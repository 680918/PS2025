import secrets
import sqlite3
from zipfile import ZipFile

import pytest

from api.asset_export import build_export
from coach.dialogue import CoachAnswer, send_dialogue
from coach.learning_topics import discussion_part, select_discussion_material, TopicBusy
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository


@pytest.fixture
def setup(tmp_path):
    materials = MaterialRepository(tmp_path / "materials.db")
    repo = CoachRepository(tmp_path / "coach.db", materials=materials)
    a = materials.add(
        "one",
        "a.txt",
        ("甲" * 800 + "乙" * 800 + "丙" * 800).encode(),
        title="相同书名",
    )
    b = materials.add(
        "one", "b.txt", ("丁" * 800 + "戊" * 800).encode(), title="相同书名"
    )
    return repo, materials, a, b


def select(repo, materials, book, part=2, now=1000):
    chunk = materials.chunks("one", book)[part - 1]
    identity = repo.select_material_part(
        "one", book, materials.get("one", book)["title"], chunk["chunk_id"], now=now
    )
    return identity, chunk


def send(
    repo,
    materials,
    *,
    action="study",
    text="",
    study_id=None,
    part_id=None,
    responder=None,
    nonce=None,
    now=1001,
):
    return send_dialogue(
        repo,
        "one",
        text,
        nonce or secrets.token_urlsafe(32),
        responder=responder or (lambda *a, **k: CoachAnswer("已讲解。")),
        materials=materials,
        action=action,
        study_id=study_id,
        part_id=part_id,
        now=now,
    )


def test_selected_part_is_exact_source_even_when_query_matches_other_text(setup):
    repo, materials, a, _ = setup
    identity, part = select(repo, materials, a)
    seen = []

    def respond(history, message, learning, *, context):
        seen.append(context)
        assert [s["source_id"] for s in context["sources"]] == [part["chunk_id"]]
        return CoachAnswer(
            "选段讲解",
            {"topic": "不能改名", "progress": "已讨论本段", "next_step": "举例"},
            [part["chunk_id"], "forged-other-source"],
        )

    assert (
        send(repo, materials, action="message", text="甲是什么", responder=respond)
        == "complete"
    )
    assert seen[0]["selected_part"]["chunk_index"] == 2
    turn = repo.view("one", now=1002)["turns"][-1]
    assert [s["source_id"] for s in turn["citations"]] == [part["chunk_id"]]
    assert discussion_part(repo, materials, "one")["chunk_id"] == part["chunk_id"]
    # A new learning title keeps the same explicitly used source part.
    assert repo.active_topic("one")["topic_id"] != identity


def test_book_positions_are_independent_and_restart_continue_restore_each_part(setup):
    repo, materials, a, b = setup
    first, part_a = select(repo, materials, a, 2)
    second, part_b = select(repo, materials, b, 1, now=1001)
    assert first != second and len(repo.list_topics("one")) == 2
    assert repo.topic("one", first)["title"] != repo.topic("one", second)["title"]
    restarted = CoachRepository(repo.database_path, materials=materials)
    observed = []

    def respond(history, message, learning, *, context):
        observed.append(context["sources"][0]["source_id"])
        return CoachAnswer("继续。")

    assert (
        send(
            restarted,
            materials,
            action="continue",
            study_id=first,
            responder=respond,
            now=1002,
        )
        == "complete"
    )
    assert observed == [part_a["chunk_id"]]
    assert (
        restarted.topic_part("one", topic_id=second)["chunk_id"] == part_b["chunk_id"]
    )
    assert materials.chunk("two", a, part_a["chunk_id"]) is None
    assert restarted.topic_part("two", topic_id=first) is None


def test_book_reuse_keeps_progress_and_does_not_replace_other_topics(setup):
    repo, materials, a, b = setup
    repo.create_topic("one", "独立主题", "", now=900)
    original = repo.active_topic("one")["topic_id"]
    first, _ = select(repo, materials, a)

    def respond(*args, **kwargs):
        return CoachAnswer(
            "讲解",
            {"topic": "错误改名", "progress": "本段已讨论", "next_step": "做一个例子"},
        )

    assert send(repo, materials, responder=respond) == "complete"
    same, _ = select(repo, materials, a, 3, now=1002)
    assert first == same and repo.active_topic("one")["progress"] == "本段已讨论"
    assert repo.topic("one", original)["material_id"] == ""
    assert len(repo.list_topics("one")) == 2


def test_stale_form_restores_its_part_and_duplicate_nonce_cannot_revert_new_choice(
    setup,
):
    repo, materials, a, _ = setup
    identity, old = select(repo, materials, a, 1)
    _, newer = select(repo, materials, a, 3, now=1001)
    calls = []

    def respond(history, message, learning, *, context):
        calls.append(context["sources"][0]["source_id"])
        return CoachAnswer("原页面选段")

    nonce = secrets.token_urlsafe(32)
    assert (
        send(
            repo,
            materials,
            study_id=identity,
            part_id=old["chunk_id"],
            responder=respond,
            nonce=nonce,
            now=1002,
        )
        == "complete"
    )
    select(repo, materials, a, 3, now=1003)
    assert (
        send(
            repo,
            materials,
            study_id=identity,
            part_id=old["chunk_id"],
            responder=respond,
            nonce=nonce,
            now=1004,
        )
        == "duplicate"
    )
    assert (
        calls == [old["chunk_id"]]
        and repo.topic_part("one")["chunk_id"] == newer["chunk_id"]
    )


def test_clearing_or_changing_material_clears_only_that_topics_pin(setup):
    repo, materials, a, b = setup
    first, _ = select(repo, materials, a)
    second, part_b = select(repo, materials, b)
    repo.activate_topic("one", first)
    select_discussion_material(repo, materials, "one", a)
    assert repo.topic_part("one") is None
    assert repo.topic_part("one", topic_id=second)["chunk_id"] == part_b["chunk_id"]
    select(repo, materials, a)
    select_discussion_material(repo, materials, "one", None)
    assert (
        repo.topic_part("one") is None
        and discussion_part(repo, materials, "one") is None
    )


def test_invalid_other_book_part_does_not_call_ai_or_mutate_state(setup):
    repo, materials, a, b = setup
    identity, selected = select(repo, materials, a)
    foreign = materials.chunks("one", b)[0]
    with pytest.raises(ValueError):
        send(repo, materials, study_id=identity, part_id=foreign["chunk_id"])
    assert repo.topic_part("one")["chunk_id"] == selected["chunk_id"]
    assert repo.view("one")["turns"] == []


def test_pending_reply_and_late_completion_cannot_change_new_source(setup):
    repo, materials, a, b = setup
    identity, _ = select(repo, materials, a)
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "pending", now=1001)
    with pytest.raises(TopicBusy):
        select(repo, materials, b, now=1002)
    assert repo.active_topic("one")["topic_id"] == identity
    new, part = select(repo, materials, b, now=1182)
    assert not repo.finish(
        "one",
        nonce,
        "late",
        {"topic": "旧回复", "progress": "旧", "next_step": "旧"},
        material_id=a,
        part_id="a" * 32,
        now=1183,
    )
    assert (
        repo.active_topic("one")["topic_id"] == new
        and repo.topic_part("one")["chunk_id"] == part["chunk_id"]
    )


def test_selection_transaction_rolls_back_topic_and_part_together(setup):
    repo, materials, a, _ = setup
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER fail_part BEFORE INSERT ON coach_topic_parts BEGIN SELECT RAISE(ABORT,'test rollback'); END"
        )
    with pytest.raises(sqlite3.Error):
        select(repo, materials, a)
    assert repo.list_topics("one") == [] and repo.active_topic("one") is None


def test_missing_chunk_never_falls_back_to_whole_book(setup):
    repo, materials, a, _ = setup
    identity, part = select(repo, materials, a)
    with sqlite3.connect(materials.database_path) as db:
        db.execute("DELETE FROM material_chunks WHERE chunk_id=?", (part["chunk_id"],))
    assert (
        send(repo, materials, action="message", text="解释资料", study_id=identity)
        == "failed"
    )
    assert repo.topic_part("one")["chunk_id"] == part["chunk_id"]


def test_export_includes_owned_actual_part_locator_and_old_database_still_works(setup):
    repo, materials, a, _ = setup
    select(repo, materials, a, 2)
    repo.create_topic("one", "不使用书籍的主题")
    archive = build_export(repo.database_path, materials.database_path, "one", ["chat"])
    try:
        with ZipFile(archive.file) as zipped:
            assert (
                "当前选段：片段 2"
                in zipped.read("学习主题/记录/学习主题目录.txt").decode()
            )
            assert (
                "讨论范围：未关联可读资料"
                in zipped.read("学习主题/记录/学习主题目录.txt").decode()
            )
    finally:
        archive.close()
    with sqlite3.connect(repo.database_path) as db:
        db.execute("DROP TABLE coach_topic_parts")
    archive = build_export(repo.database_path, materials.database_path, "one", ["chat"])
    archive.close()


def test_reviewing_saved_lesson_preserves_original_and_other_topic_pins(setup):
    repo, materials, a, b = setup
    first, part_a = select(repo, materials, a)
    second, part_b = select(repo, materials, b)
    repo.activate_topic("one", first)
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "整理教案", now=1000)
    repo.finish(
        "one",
        nonce,
        "确认草稿",
        None,
        now=1001,
        draft={
            "title": "教案",
            "topic": repo.topic("one", first)["title"],
            "content": "已保存的内容。",
        },
    )
    lesson = repo.list_knowledge("one", status="pending")[0]["knowledge_id"]
    repo.confirm_knowledge("one", lesson)
    repo.select_review("one", lesson, material_id=a)
    assert repo.topic_part("one")["chunk_id"] == part_a["chunk_id"]
    assert repo.topic_part("one", topic_id=second)["chunk_id"] == part_b["chunk_id"]
