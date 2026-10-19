import secrets
import sqlite3

import pytest

from conversation.coach_repository import CoachRepository, PENDING_LIFETIME


def test_status_read_distinguishes_admission_result_and_expiry_without_changing_records(
    tmp_path,
):
    repo = CoachRepository(tmp_path / "coach.db")
    missing, pending, failed, complete = [secrets.token_urlsafe(32) for _ in range(4)]
    for user, nonce in [
        ("one", pending),
        ("one-fail", failed),
        ("one-complete", complete),
    ]:
        assert (
            repo.claim(user, nonce, "私人提问", now=1000, ai_kind="dialogue")
            == "claimed"
        )
    repo.fail("one-fail", failed, now=1002)
    assert repo.finish("one-complete", complete, "有效回复", None, now=1002)
    before = repo.database_path.read_bytes()
    assert repo.dialogue_status("one", missing, now=1001) == {"status": "missing"}
    assert repo.dialogue_status("one", pending, now=1001) == {"status": "pending"}
    assert repo.dialogue_status("one", pending, now=1000 + PENDING_LIFETIME - 1) == {
        "status": "pending"
    }
    assert repo.dialogue_status("one", pending, now=1000 + PENDING_LIFETIME) == {
        "status": "expired"
    }
    assert repo.dialogue_status("one-fail", failed, now=2000) == {"status": "failed"}
    assert repo.dialogue_status("one-complete", complete, now=2000) == {
        "status": "complete"
    }
    assert repo.database_path.read_bytes() == before
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT status FROM coach_turns WHERE nonce=?", (pending,)
            ).fetchone()[0]
            == "pending"
        )
        assert db.execute("SELECT COUNT(*) FROM coach_turns").fetchone()[0] == 3


def test_other_account_nonce_has_same_missing_response_and_checks_do_not_use_daily_quota(
    tmp_path,
):
    repo = CoachRepository(tmp_path / "coach.db")
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "不能透露的正文", now=1000, ai_kind="dialogue")
    usage = repo.ai_usage("one", now=1001)
    before = repo.database_path.read_bytes()
    for _ in range(25):
        assert repo.dialogue_status("two", nonce, now=1001) == {"status": "missing"}
        assert repo.dialogue_status("one", nonce, now=1001) == {"status": "pending"}
    assert repo.ai_usage("one", now=1001) == usage
    assert repo.database_path.read_bytes() == before


def test_status_survives_reopening_without_resending_and_completed_nonce_stays_idempotent(
    tmp_path,
):
    path = tmp_path / "coach.db"
    repo = CoachRepository(path)
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "问题", now=1000, ai_kind="dialogue")
    repo.finish("one", nonce, "回复", None, now=1001)
    reopened = CoachRepository(path)
    assert reopened.dialogue_status("one", nonce, now=1002) == {"status": "complete"}
    assert (
        reopened.claim("one", nonce, "问题", now=1003, ai_kind="dialogue")
        == "duplicate"
    )
    assert len(reopened.view("one", now=1003)["turns"]) == 1


@pytest.mark.parametrize(
    "nonce", [None, 4, "short", "x" * 44, "x" * 42 + "!", "x" * 42 + "\n", "中" * 43]
)
def test_status_rejects_invalid_nonce_without_database_changes(tmp_path, nonce):
    repo = CoachRepository(tmp_path / "coach.db")
    before = repo.database_path.read_bytes()
    with pytest.raises(ValueError):
        repo.dialogue_status("one", nonce)
    assert repo.database_path.read_bytes() == before
