import secrets
import sqlite3

import pytest

from coach.draft_edit import draft_version
from conversation.coach_repository import CoachRepository
from tests.test_lesson_revision import saved_lesson


@pytest.fixture
def setup(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    identity = saved_lesson(repo)
    return repo, identity


def test_origin_is_bounded_owned_and_does_not_return_private_request_fields(setup):
    repo, identity = setup
    item = repo.knowledge("one", identity)
    text = "请把刚才的讨论整理成教案。" + "回想再实践" * 100
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_turns SET user_content=? WHERE turn_id=?",
            (text, item["turn_id"]),
        )
    before = repo.database_path.read_bytes()
    origin = repo.knowledge_origin("one", identity)
    assert set(origin) == {
        "turn_id",
        "created_at",
        "status",
        "user_excerpt",
        "truncated",
    }
    assert origin == dict(
        turn_id=item["turn_id"],
        created_at=1000,
        status="complete",
        user_excerpt=text[:180],
        truncated=True,
    )
    assert repo.database_path.read_bytes() == before
    assert (
        CoachRepository(repo.database_path).knowledge_origin("one", identity) == origin
    )
    assert repo.knowledge_origin("other", identity) is None


def test_revision_and_confirmation_keep_original_source_and_not_later_conversation(
    setup,
):
    repo, identity = setup
    before = repo.knowledge_origin("one", identity)
    saved_lesson(repo, title="后来另一篇教案")
    assert (
        repo.revise_knowledge(
            "one", identity, 1, title="修订后标题", content="新的正文", now=2000
        )
        == "updated"
    )
    assert repo.knowledge_origin("one", identity) == before
    draft = saved_lesson(repo, title="待确认的内容", save=False)
    original = repo.knowledge_origin("one", draft)
    assert (
        original
        and original["user_excerpt"] == "整理教案"
        and original["truncated"] is False
    )
    repo.confirm_knowledge("one", draft)
    assert repo.knowledge_origin("one", draft) == original


def test_missing_or_foreign_turn_is_not_replaced_by_another_source(setup):
    repo, identity = setup
    foreign = saved_lesson(
        repo, user="other", title="他人私有教案", content="PRIVATE_FOREIGN_CONTENT"
    )
    turn = repo.knowledge("other", foreign)["turn_id"]
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_knowledge SET turn_id=? WHERE knowledge_id=?",
            (turn, identity),
        )
    assert repo.knowledge_origin("one", identity) is None
    assert repo.knowledge("one", identity)["title"] == "原版教案"
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_knowledge SET turn_id=? WHERE knowledge_id=?",
            (turn + 999, identity),
        )
    assert repo.knowledge_origin("one", identity) is None


@pytest.mark.parametrize("identity", ["", "../private", "b" * 32, None])
def test_missing_or_invalid_lesson_has_no_origin(setup, identity):
    repo, _ = setup
    assert repo.knowledge_origin("one", identity) is None


def test_dismissed_draft_is_not_an_origin_entry_until_explicitly_restored(setup):
    repo, _ = setup
    identity = saved_lesson(repo, title="已移出草稿", save=False)
    origin = repo.knowledge_origin("one", identity)
    repo.confirm_knowledge("one", identity, save=False)
    assert repo.knowledge_origin("one", identity) is None
    removed = repo.knowledge("one", identity, include_dismissed=True)
    assert repo.restore_draft("one", identity, draft_version(removed)) == "restored"
    assert repo.knowledge_origin("one", identity) == origin


def test_origin_reads_leave_expired_pending_request_learning_and_usage_unchanged(setup):
    repo, identity = setup
    repo.create_topic("one", "当前学习位置", now=2000)
    nonce = secrets.token_urlsafe(32)
    assert (
        repo.claim("one", nonce, "尚未完成", now=2001, ai_kind="dialogue") == "claimed"
    )
    before = repo.database_path.read_bytes()
    assert repo.knowledge_origin("one", identity)
    assert repo.active_topic("one")["title"] == "当前学习位置"
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT status FROM coach_turns WHERE nonce=?", (nonce,)
            ).fetchone()[0]
            == "pending"
        )
        assert db.execute("SELECT count(*) FROM coach_ai_usage").fetchone()[0] == 1
    assert repo.database_path.read_bytes() == before
