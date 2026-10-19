import secrets
import sqlite3
from contextlib import closing
from time import time

import pytest

from coach.dialogue import CoachAnswer, send_dialogue
from coach.learning_topics import TopicBusy
from conversation.coach_repository import CoachRepository
from tests import test_book_section as section_tests

setup = section_tests.setup


def saved_review(repo, materials, book, *, title="回想教案"):
    topic_id, part = section_tests.select(repo, materials, book)
    row = repo.topic("one", topic_id)
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "整理", now=1001)
    sources = [
        {
            "source_id": "review-source",
            "material_id": book,
            "title": "整理时原书",
            "locator": "片段 1",
            "excerpt": "教案实际引用的依据。",
        }
    ]
    repo.finish(
        "one",
        nonce,
        "准备确认",
        {
            "topic": row["title"],
            "progress": "已讨论到第三个例子。",
            "next_step": "继续原书第二段。",
        },
        now=1002,
        material_id=book,
        part_id=part["chunk_id"],
        draft={
            "title": title,
            "topic": row["title"],
            "content": "# 知识点\n先回想再实践。",
        },
        citations=sources,
    )
    identity = repo.list_knowledge("one", status="pending")[0]["knowledge_id"]
    repo.confirm_knowledge("one", identity)
    return identity, topic_id, part


def test_start_and_end_preserve_existing_progress_book_and_part(setup):
    repo, materials, a, b = setup
    identity, topic_id, part = saved_review(repo, materials, a)
    before = repo.topic("one", topic_id)
    second, other_part = section_tests.select(repo, materials, b)
    other_before = repo.topic("one", second)
    repo.select_review("one", identity, material_id=b)
    assert repo.active_topic("one") == before
    assert repo.topic_part("one")["chunk_id"] == part["chunk_id"]
    assert repo.topic("one", second) == other_before
    assert repo.topic_part("one", topic_id=second)["chunk_id"] == other_part["chunk_id"]
    state = repo.review_state("one")
    assert repo.end_review("one", identity, state["revision"]) == "ended"
    assert repo.review("one") is None and repo.active_topic("one") == before
    assert repo.topic_part("one")["chunk_id"] == part["chunk_id"]
    assert repo.end_review("one", identity, state["revision"]) == "conflict"


def test_review_context_uses_saved_sources_and_ignores_model_progress(setup):
    repo, materials, a, _ = setup
    identity, topic_id, part = saved_review(repo, materials, a)
    before = repo.topic("one", topic_id)
    repo.select_review("one", identity)
    seen = []

    def respond(*a, context):
        seen.append(context)
        return CoachAnswer(
            "从这个例子重温。",
            {
                "topic": "模型另建主题",
                "progress": "错误覆盖",
                "next_step": "错误下一步",
            },
            ["review-source"],
        )

    result = send_dialogue(
        repo,
        "one",
        "请解释这份教案",
        secrets.token_urlsafe(32),
        responder=respond,
        materials=materials,
    )
    assert result == "complete" and len(seen) == 1
    assert seen[0]["review"]["title"] == "回想教案"
    assert seen[0]["material"] is None and seen[0]["selected_part"] is None
    assert seen[0]["sources"] == repo.knowledge("one", identity)["citations"]
    assert (
        repo.topic("one", topic_id) == before
        and repo.topic_part("one")["chunk_id"] == part["chunk_id"]
    )
    assert len(repo.list_topics("one")) == 1


def test_explicit_study_exits_review_and_uses_original_selected_part(setup):
    repo, materials, a, _ = setup
    identity, topic_id, part = saved_review(repo, materials, a)
    repo.select_review("one", identity)
    seen = []
    result = send_dialogue(
        repo,
        "one",
        "",
        secrets.token_urlsafe(32),
        action="study",
        study_id=topic_id,
        part_id=part["chunk_id"],
        review_guard=repo.review_state("one"),
        materials=materials,
        responder=lambda *a, context: (
            seen.append(context)
            or CoachAnswer("原选段讲解。", None, [part["chunk_id"]])
        ),
    )
    assert result == "complete" and repo.review("one") is None
    assert (
        seen[0]["review"] is None
        and seen[0]["sources"][0]["source_id"] == part["chunk_id"]
    )


def test_review_works_without_material_repository_and_continue_has_review_intro(setup):
    repo, materials, a, _ = setup
    identity, _, _ = saved_review(repo, materials, a)
    repo.select_review("one", identity)

    def respond(*a, context):
        assert context["review"]["title"] == "回想教案"
        return CoachAnswer("## 先把位置对齐\n一起看核心方法。")

    assert (
        send_dialogue(
            repo,
            "one",
            "",
            secrets.token_urlsafe(32),
            action="continue",
            responder=respond,
        )
        == "complete"
    )
    assert repo.view("one")["turns"][-1]["assistant_content"].startswith(
        "我们继续重温《回想教案》。"
    )


def test_busy_exit_and_selection_fail_without_changing_session(setup):
    repo, materials, a, _ = setup
    identity, _, _ = saved_review(repo, materials, a)
    repo.select_review("one", identity)
    state = repo.review_state("one")
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "正在回复", now=int(time()))
    with pytest.raises(TopicBusy):
        repo.end_review("one", identity, state["revision"])
    with pytest.raises(TopicBusy):
        repo.select_review("one", identity)
    assert repo.review_state("one") == state
    repo.fail("one", nonce, now=int(time()))
    assert repo.end_review("one", identity, state["revision"]) == "ended"


def test_stale_exit_and_composer_guards_do_not_touch_newer_state_or_quota(setup):
    repo, materials, a, b = setup
    first, _, _ = saved_review(repo, materials, a)
    second, _, _ = saved_review(repo, materials, b, title="另一份教案")
    empty = repo.review_state("one")
    repo.select_review("one", first)
    old = repo.review_state("one")
    repo.select_review("one", second)
    repo.select_review("one", first)
    state = repo.review_state("one")
    before = repo.database_path.read_bytes()
    assert repo.end_review("one", first, old["revision"]) == "conflict"
    assert repo.end_review("two", first, state["revision"]) == "conflict"
    assert repo.database_path.read_bytes() == before
    calls = []
    usage = repo.ai_usage("one")
    for guard in [empty, old]:
        assert (
            send_dialogue(
                repo,
                "one",
                "不能发出",
                secrets.token_urlsafe(32),
                responder=lambda *a, **k: calls.append(True),
                materials=materials,
                review_guard=guard,
            )
            == "review_changed"
        )
    assert calls == [] and repo.ai_usage("one")["used"] == usage["used"]
    assert repo.review_state("one") == state


def test_legacy_review_and_generation_rollback_survive_restart(setup):
    repo, materials, a, _ = setup
    identity, _, _ = saved_review(repo, materials, a)
    repo.select_review("one", identity)
    with closing(repo._connect()) as db, db:
        db.execute("DROP TABLE coach_review_versions")
    restarted = CoachRepository(repo.database_path)
    assert restarted.review_state("one") == {"knowledge_id": identity, "revision": 0}
    assert restarted.end_review("one", identity, 0) == "ended"
    restarted.select_review("one", identity)
    state = restarted.review_state("one")
    with closing(repo._connect()) as db, db:
        db.execute(
            "CREATE TRIGGER reject_review BEFORE INSERT ON coach_review BEGIN SELECT RAISE(ABORT,'test failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        restarted.select_review("one", identity)
    assert restarted.review_state("one") == state
