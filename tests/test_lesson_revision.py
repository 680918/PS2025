import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from zipfile import ZipFile

import pytest

from api.asset_export import build_export
from coach.dialogue import CoachAnswer, send_dialogue
from coach.learning_topics import TopicBusy
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository


def saved_lesson(
    repo, user="one", title="原版教案", content="# 原文\n最初的例子。", save=True
):
    nonce = secrets.token_urlsafe(32)
    repo.claim(user, nonce, "整理教案", now=1000)
    repo.finish(
        user,
        nonce,
        "请确认草稿。",
        None,
        now=1001,
        draft={"title": title, "topic": "学习方法", "content": content},
        citations=[
            {
                "source_id": "source",
                "material_id": "book",
                "title": "参考资料",
                "locator": "片段 1",
                "excerpt": "原始依据",
            }
        ],
    )
    identity = repo.list_knowledge(user, status="pending")[0]["knowledge_id"]
    if save:
        repo.confirm_knowledge(user, identity)
    return identity


@pytest.fixture
def setup(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    identity = saved_lesson(repo)
    return repo, identity


def test_original_compatibility_reads_do_not_write_then_revise_and_restore_keep_all_versions(
    setup,
):
    repo, identity = setup
    original = repo.knowledge("one", identity)
    before = repo.database_path.read_bytes()
    assert original["revision"] == 1
    assert repo.knowledge_versions("one", identity)[0]["revision"] == 1
    assert repo.knowledge_version("one", identity, 1)["content"] == original["content"]
    assert repo.database_path.read_bytes() == before
    assert (
        repo.revise_knowledge(
            "one", identity, 1, title=" 新教案 ", content=" 新的例子。 ", now=2000
        )
        == "updated"
    )
    latest = repo.knowledge("one", identity)
    assert (
        latest["title"],
        latest["content"],
        latest["revision"],
        latest["revised_at"],
    ) == ("新教案", "新的例子。", 2, 2000)
    assert all(
        latest[key] == original[key]
        for key in ("topic", "saved_at", "created_at", "citations")
    )
    assert repo.knowledge_version("one", identity, 1)["content"] == original["content"]
    assert repo.revise_knowledge("one", identity, 2, restore=1, now=2001) == "updated"
    versions = repo.knowledge_versions("one", identity)
    assert [v["revision"] for v in versions] == [3, 2, 1]
    assert versions[0]["restored_from"] == 1
    assert repo.knowledge("one", identity)["content"] == original["content"]
    assert repo.knowledge_version("one", identity, 2)["content"] == "新的例子。"
    restarted = CoachRepository(repo.database_path)
    assert restarted.knowledge("one", identity)["revision"] == 3


def test_unchanged_replays_and_stale_edit_do_not_make_duplicate_versions(setup):
    repo, identity = setup
    item = repo.knowledge("one", identity)
    assert (
        repo.revise_knowledge(
            "one", identity, 1, title=item["title"], content=item["content"]
        )
        == "unchanged"
    )
    assert repo.revise_knowledge("one", identity, 1, restore=1) == "unchanged"
    assert (
        repo.revise_knowledge("one", identity, 1, title="新版", content="新内容")
        == "updated"
    )
    assert (
        repo.revise_knowledge("one", identity, 1, title="旧页面", content="旧页面内容")
        == "conflict"
    )
    assert repo.revise_knowledge("one", identity, 2, restore=2) == "unchanged"
    assert len(repo.knowledge_versions("one", identity)) == 2


def test_concurrent_edits_preserve_original_and_exactly_one_new_revision(setup):
    repo, identity = setup
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda text: repo.revise_knowledge(
                    "one", identity, 1, title=text, content=text
                ),
                ["A", "B"],
            )
        )
    assert sorted(results) == ["conflict", "updated"]
    assert repo.knowledge("one", identity)["title"] in {"A", "B"}
    assert repo.knowledge_version("one", identity, 1)["title"] == "原版教案"
    assert len(repo.knowledge_versions("one", identity)) == 2


def test_revision_and_original_snapshot_roll_back_if_current_update_fails(setup):
    repo, identity = setup
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER fail_revision BEFORE UPDATE ON coach_knowledge BEGIN SELECT RAISE(ABORT,'test rollback'); END"
        )
    with pytest.raises(sqlite3.Error):
        repo.revise_knowledge("one", identity, 1, title="新标题", content="新内容")
    assert repo.knowledge("one", identity)["revision"] == 1
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute("SELECT COUNT(*) FROM coach_knowledge_versions").fetchone()[0]
            == 0
        )


def test_ownership_pending_and_missing_restore_cannot_modify_saved_lesson(setup):
    repo, identity = setup
    assert repo.knowledge_version("two", identity, 1) is None
    assert repo.knowledge_versions("two", identity) == []
    assert (
        repo.revise_knowledge("two", identity, 1, title="x", content="x") == "missing"
    )
    assert repo.revise_knowledge("one", identity, 1, restore=99) == "missing"
    draft = saved_lesson(repo, save=False)
    assert repo.revise_knowledge("one", draft, 1, title="x", content="x") == "missing"
    assert repo.knowledge_versions("one", draft) == []
    assert repo.knowledge("one", identity)["revision"] == 1


@pytest.mark.parametrize(
    "values",
    [
        {"title": "", "content": "x"},
        {"title": "x" * 121, "content": "x"},
        {"title": "x", "content": " "},
        {"title": "x", "content": "x" * 12001},
        {"title": "a\nb", "content": "x"},
        {"title": "x", "content": "\x00"},
        {"title": "\ud800", "content": "x"},
        {"title": None, "content": "x"},
        {"restore": True},
        {"restore": -1},
        {"restore": 1, "title": "x"},
    ],
)
def test_bad_input_does_not_change_original(setup, values):
    repo, identity = setup
    with pytest.raises(ValueError):
        repo.revise_knowledge("one", identity, 1, **values)
    assert repo.knowledge("one", identity)["revision"] == 1


def test_current_review_waits_until_reply_complete_before_revision(setup):
    repo, identity = setup
    repo.select_review("one", identity)
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "正在重温", now=1000)
    with pytest.raises(TopicBusy):
        repo.revise_knowledge(
            "one", identity, 1, title="新", content="新内容", now=1001
        )
    assert repo.knowledge("one", identity)["revision"] == 1
    repo.finish("one", nonce, "完成", None, now=1002)
    assert (
        repo.revise_knowledge(
            "one", identity, 1, title="新", content="新内容", now=1003
        )
        == "updated"
    )


def test_review_model_context_search_and_exports_use_current_content(setup, tmp_path):
    repo, identity = setup
    materials = MaterialRepository(tmp_path / "materials.db")
    repo.revise_knowledge(
        "one", identity, 1, title="新的独有标题", content="# 最新例子\n内容已修正。"
    )
    repo.select_review("one", identity)
    seen = []

    def respond(history, message, learning, *, context):
        seen.append(context["review"])
        assert not context["draft_requested"] and not context["can_suggest_draft"]
        return CoachAnswer("好的。")

    assert (
        send_dialogue(
            repo,
            "one",
            "请重温这份教案",
            secrets.token_urlsafe(32),
            responder=respond,
            materials=materials,
        )
        == "complete"
    )
    assert seen[0]["title"] == "新的独有标题" and "内容已修正" in seen[0]["content"]
    assert "本次没有生成" not in repo.view("one")["turns"][-1]["assistant_content"]
    assert (
        repo.list_knowledge("one", query="新的独有标题")[0]["knowledge_id"] == identity
    )
    archive = build_export(
        repo.database_path, materials.database_path, "one", ["saved"]
    )
    try:
        with ZipFile(archive.file) as zipped:
            text = "\n".join(
                zipped.read(name).decode()
                for name in zipped.namelist()
                if name.endswith((".md", ".html"))
            )
            assert (
                "新的独有标题" in text
                and "内容已修正" in text
                and "最初的例子" not in text
            )
    finally:
        archive.close()


def test_many_revisions_are_paginated_without_loading_all_bodies(setup):
    repo, identity = setup
    for revision in range(1, 24):
        repo.revise_knowledge(
            "one",
            identity,
            revision,
            title=f"第{revision + 1}版",
            content=f"内容{revision + 1}",
        )
    assert len(repo.knowledge_versions("one", identity)) == 21
    older = repo.knowledge_versions("one", identity, offset=20)
    assert [v["revision"] for v in older] == [4, 3, 2, 1]
    assert "content" not in older[0]


def test_opening_pre_revision_database_preserves_existing_lesson_row(setup):
    repo, identity = setup
    with sqlite3.connect(repo.database_path) as db:
        original = db.execute("SELECT * FROM coach_knowledge").fetchall()
        db.execute("DROP TABLE coach_knowledge_versions")
    migrated = CoachRepository(repo.database_path)
    assert migrated.knowledge("one", identity)["revision"] == 1
    with sqlite3.connect(repo.database_path) as db:
        assert db.execute("SELECT * FROM coach_knowledge").fetchall() == original


@pytest.mark.parametrize(
    "message,requested",
    [
        ("请重温这份教案", False),
        ("解释教案中的例子", False),
        ("这份教案可以怎么复习", False),
        ("请重新整理这份教案，方便复习", True),
        ("把这个知识点整理成教案", True),
    ],
)
def test_reading_a_lesson_is_not_a_new_draft_request(
    setup, tmp_path, message, requested
):
    repo, identity = setup
    repo.select_review("one", identity)
    materials = MaterialRepository(tmp_path / "materials.db")

    def respond(history, text, learning, *, context):
        assert context["draft_requested"] is requested
        return CoachAnswer("已阅读当前版本。")

    assert (
        send_dialogue(
            repo,
            "one",
            message,
            secrets.token_urlsafe(32),
            responder=respond,
            materials=materials,
        )
        == "complete"
    )
