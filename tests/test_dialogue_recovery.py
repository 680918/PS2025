import secrets
import sqlite3

import pytest

from conversation.coach_repository import CoachRepository, PENDING_LIFETIME


def test_existing_chat_is_migrated_once_into_a_history_conversation(tmp_path):
    path = tmp_path / "legacy-coach.db"
    nonce = secrets.token_urlsafe(32)
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE coach_turns (
                turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL, nonce TEXT NOT NULL,
                user_content TEXT NOT NULL, assistant_content TEXT,
                status TEXT NOT NULL, created_at INTEGER NOT NULL,
                completed_at INTEGER, UNIQUE(user_id, nonce)
            );
            CREATE TABLE coach_learning (
                user_id TEXT PRIMARY KEY, topic TEXT NOT NULL,
                progress TEXT NOT NULL, next_step TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            """
        )
        db.execute(
            "INSERT INTO coach_turns VALUES(NULL,?,?,?,?,?,?,?)",
            ("one", nonce, "旧问题", "旧回复", "complete", 1000, 1001),
        )
        db.execute(
            "INSERT INTO coach_learning VALUES(?,?,?,?,?)",
            ("one", "旧主题", "旧进度", "旧下一步", 1001),
        )

    upgraded = CoachRepository(path)
    view = upgraded.view("one", now=1002)
    assert [turn["user_content"] for turn in view["turns"]] == ["旧问题"]
    assert view["conversation"]["title"] == "历史对话"
    assert view["conversation"]["topic_id"] == upgraded.active_topic("one")["topic_id"]
    assert view["conversations"][0]["turn_count"] == 1

    reopened = CoachRepository(path)
    assert reopened.view("one", now=1003)["conversation"] == view["conversation"]
    assert len(reopened.conversations("one")) == 1


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
