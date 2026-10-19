import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from coach.draft_edit import draft_version
from conversation.coach_repository import CoachRepository
from tests.test_lesson_revision import saved_lesson


def seed(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    identity = saved_lesson(repo, save=False)
    return repo, identity, repo.knowledge("one", identity)


def test_stage_is_persistent_pending_and_preserves_sources_history_usage_and_links(
    tmp_path,
):
    repo, identity, item = seed(tmp_path)
    turns = repo.view("one", now=1002)["turns"]
    usage = repo.ai_usage("one", now=1002)
    assert (
        repo.change_draft(
            "one",
            identity,
            "stage",
            draft_version(item),
            title=" 新草稿 ",
            content="# 新正文\r\n继续整理。",
        )
        == "staged"
    )
    restarted = CoachRepository(repo.database_path)
    current = restarted.knowledge("one", identity)
    assert current["title"] == "新草稿" and current["content"] == "# 新正文\n继续整理。"
    assert current["status"] == "pending" and current["saved_at"] is None
    assert (
        current["citations"] == item["citations"]
        and current["created_at"] == item["created_at"]
    )
    assert current["topic"] == item["topic"] and current["turn_id"] == item["turn_id"]
    assert (
        restarted.view("one", now=1002)["turns"] == turns
        and restarted.ai_usage("one", now=1002) == usage
    )
    assert (
        restarted.list_knowledge("one") == []
        and restarted.knowledge_versions("one", identity) == []
    )
    assert (
        restarted.list_knowledge("one", status="pending", query="继续整理")[0][
            "knowledge_id"
        ]
        == identity
    )
    assert (
        restarted.change_draft(
            "one",
            identity,
            "save",
            draft_version(current),
            title=current["title"],
            content=current["content"],
        )
        == "saved_now"
    )
    assert (
        restarted.knowledge("one", identity, saved_only=True)["content"]
        == current["content"]
    )
    assert (
        restarted.knowledge_version("one", identity, 1)["content"] == current["content"]
    )


@pytest.mark.parametrize("operation", ["stage", "save", "dismiss"])
def test_stale_actions_cannot_overwrite_confirm_or_hide_newer_draft(
    tmp_path, operation
):
    repo, identity, item = seed(tmp_path)
    repo.change_draft(
        "one", identity, "stage", draft_version(item), title="新版", content="新的内容"
    )
    current = repo.knowledge("one", identity)
    assert (
        repo.change_draft(
            "one",
            identity,
            operation,
            draft_version(item),
            title="旧页面",
            content="旧内容",
        )
        == "conflict"
    )
    assert repo.knowledge("one", identity) == current


def test_saved_draft_can_never_be_demoted_overwritten_or_dismissed_by_old_page(
    tmp_path,
):
    repo, identity, item = seed(tmp_path)
    repo.change_draft(
        "one",
        identity,
        "save",
        draft_version(item),
        title="正式教案",
        content="确认正文",
    )
    current = repo.knowledge("one", identity)
    for operation in ("stage", "save", "dismiss"):
        assert (
            repo.change_draft(
                "one",
                identity,
                operation,
                draft_version(item),
                title="旧页面",
                content="不能覆盖",
            )
            == "saved"
        )
    assert repo.knowledge("one", identity) == current


def test_owner_noop_and_dismiss_are_checked_without_touching_other_records(tmp_path):
    repo, identity, item = seed(tmp_path)
    assert (
        repo.change_draft(
            "two",
            identity,
            "stage",
            draft_version(item),
            title="别人的",
            content="内容",
        )
        == "missing"
    )
    before = repo.database_path.read_bytes()
    assert (
        repo.change_draft(
            "one",
            identity,
            "stage",
            draft_version(item),
            title=item["title"],
            content=item["content"],
        )
        == "unchanged"
    )
    assert repo.database_path.read_bytes() == before
    assert (
        repo.change_draft("one", identity, "dismiss", draft_version(item))
        == "dismissed"
    )
    assert repo.knowledge("one", identity) is None
    assert (
        repo.change_draft(
            "one",
            identity,
            "stage",
            draft_version(item),
            title="不能恢复",
            content="内容",
        )
        == "missing"
    )


@pytest.mark.parametrize(
    "title,content",
    [
        ("", "x"),
        ("x" * 121, "x"),
        ("bad\nname", "x"),
        ("name", ""),
        ("name", "x" * 12001),
        ("name", "bad\x00body"),
        ("name", "bad\ud800"),
    ],
)
def test_invalid_draft_inputs_do_not_change_state(tmp_path, title, content):
    repo, identity, item = seed(tmp_path)
    with pytest.raises(ValueError):
        repo.change_draft(
            "one", identity, "stage", draft_version(item), title=title, content=content
        )
    assert repo.knowledge("one", identity) == item


def test_conflict_precedes_invalid_input_and_transaction_rolls_back_on_failure(
    tmp_path,
):
    repo, identity, item = seed(tmp_path)
    repo.change_draft(
        "one", identity, "stage", draft_version(item), title="新版", content="新内容"
    )
    assert (
        repo.change_draft(
            "one", identity, "stage", draft_version(item), title="", content=""
        )
        == "conflict"
    )
    current = repo.knowledge("one", identity)
    with closing(repo._connect()) as db, db:
        db.execute(
            "CREATE TRIGGER stop_stage BEFORE UPDATE ON coach_knowledge BEGIN SELECT RAISE(ABORT,'test failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        repo.change_draft(
            "one",
            identity,
            "save",
            draft_version(current),
            title="新标题",
            content="新正文",
        )
    assert repo.knowledge("one", identity) == current


def test_concurrent_stage_and_confirmation_have_only_one_effect(tmp_path):
    repo, identity, item = seed(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda operation: repo.change_draft(
                    "one",
                    identity,
                    operation,
                    draft_version(item),
                    title="暂存标题" if operation == "stage" else item["title"],
                    content="暂存内容" if operation == "stage" else item["content"],
                ),
                ["stage", "save"],
            )
        )
    current = repo.knowledge("one", identity)
    assert (
        results == ["staged", "conflict"]
        and current["status"] == "pending"
        and current["content"] == "暂存内容"
    ) or (
        results == ["saved", "saved_now"]
        and current["status"] == "saved"
        and current["content"] == item["content"]
    )
