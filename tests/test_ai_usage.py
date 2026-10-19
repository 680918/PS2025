import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from threading import Event

import pytest

from coach.ai_usage import ZONE, validate_limits
from coach.dialogue import CoachAnswer, send_dialogue
from conversation.coach_repository import CoachRepository
from tests import test_unit_lessons as unit_tests
from tests import test_local_backup as backups

space = backups.space
password_hash = backups.password_hash


def limits(repo, user=2, total=10):
    validate_limits(user, total)
    with closing(repo._connect()) as db, db:
        db.execute(
            "INSERT OR REPLACE INTO coach_ai_limits VALUES(1,?,?)", (user, total)
        )


def send(
    repo, text="学习这个知识点", *, user="one", now=1000, nonce=None, responder=None
):
    return send_dialogue(
        repo,
        user,
        text,
        nonce or secrets.token_urlsafe(32),
        now=now,
        responder=responder or (lambda *a, **k: CoachAnswer("回答")),
    )


@pytest.fixture
def repo(tmp_path):
    return CoachRepository(tmp_path / "coach.db")


def test_rejected_calls_do_not_change_turns_topic_or_user_input_and_restarts_keep_counts(
    repo,
):
    limits(repo, user=1)
    calls = []
    assert (
        send(repo, responder=lambda *a, **k: calls.append(1) or CoachAnswer("回答"))
        == "complete"
    )
    repo.create_topic("one", "之前学习的主题", now=1002)
    a = repo.active_topic("one")
    repo.create_topic("one", "目前学习的主题", now=1003)
    before = repo.database_path.read_bytes()
    result = send_dialogue(
        repo,
        "one",
        "这次要保留的消息",
        secrets.token_urlsafe(32),
        responder=lambda *a, **k: pytest.fail("must not call"),
        study_id=a["topic_id"],
        now=1004,
    )
    assert result == "daily_limit" and calls == [1]
    assert repo.database_path.read_bytes() == before
    assert repo.active_topic("one")["title"] == "目前学习的主题"
    assert CoachRepository(repo.database_path).ai_usage("one", now=1004)["used"] == 1
    assert send(CoachRepository(repo.database_path), now=1005) == "daily_limit"


def test_duplicate_and_busy_calls_do_not_consume_another_slot(repo):
    limits(repo, user=3)
    nonce = secrets.token_urlsafe(32)
    assert send(repo, nonce=nonce) == "complete"
    assert send(repo, nonce=nonce) == "duplicate"
    pending = secrets.token_urlsafe(32)
    assert repo.claim("one", pending, "等待", now=1001, ai_kind="dialogue") == "claimed"
    assert send(repo, now=1002) == "busy"
    assert repo.ai_usage("one", now=1002)["used"] == 2


@pytest.mark.parametrize("failure", ["exception", "invalid", "late"])
def test_failed_invalid_and_late_replies_keep_the_admission_count(repo, failure):
    limits(repo, user=1)

    def respond(*args, **kwargs):
        if failure == "exception":
            raise RuntimeError("private provider secret")
        if failure == "invalid":
            return object()
        repo.view("one", now=1200)
        return CoachAnswer("迟到的回复")

    assert send(repo, responder=respond) in {"failed", "interrupted"}
    assert repo.ai_usage("one", now=1201)["used"] == 1
    assert send(repo, now=1202) == "daily_limit"
    assert "private provider secret" not in str(repo.view("one", now=1202))


def test_explicit_memory_remains_available_without_model_calls_when_paused(repo):
    limits(repo, user=0, total=0)
    before = repo.ai_usage("one", now=1000)
    assert (
        send(
            repo,
            "请记住，解释时多用生活中的例子。",
            responder=lambda *a, **k: pytest.fail("no model"),
        )
        == "complete"
    )
    assert repo.list_memories("one")[0]["content"] == "解释时多用生活中的例子。"
    assert repo.ai_usage("one", now=1000) == before
    assert send(repo) == "daily_limit"


def test_book_unit_and_dialogue_share_counts_and_summary_replay_is_free(tmp_path):
    setup = unit_tests.setup.__wrapped__(tmp_path)
    repo = setup[0]
    limits(repo, user=2)
    assert send(repo) == "complete"
    nonce = secrets.token_urlsafe(32)
    assert unit_tests.send(setup, nonce=nonce) == "complete"
    assert unit_tests.send(setup, nonce=nonce) == "duplicate"
    assert unit_tests.send(setup, batch=2) == "daily_limit"
    snapshot = repo.ai_usage("one", now=1003)
    assert snapshot["used"] == 2
    assert {row["kind"] for row in snapshot["recent"]} == {"dialogue", "unit_lesson"}
    assert len(repo.list_knowledge("one", status="pending")) == 1


def test_concurrent_accounts_cannot_overrun_the_shared_daily_limit(repo):
    limits(repo, user=3, total=3)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda number: send(
                    CoachRepository(repo.database_path), user=f"user{number}"
                ),
                range(8),
            )
        )
    assert results.count("complete") == 3 and results.count("daily_limit") == 5
    with closing(repo._connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM coach_ai_usage").fetchone()[0] == 3
    assert repo.ai_usage("someone", now=1000)["reason"] == "space"
    assert "space_used" not in repo.ai_usage("someone", now=1000)


def test_same_account_inflight_and_late_completion_do_not_refund_or_overwrite(repo):
    limits(repo, user=2)
    ready, release = Event(), Event()

    def respond(*args, **kwargs):
        ready.set()
        assert release.wait(5)
        return CoachAnswer("迟到")

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(send, repo, responder=respond)
        assert ready.wait(5)
        assert send(repo, now=1001) == "busy"
        repo.view("one", now=1200)
        assert send(repo, now=1201) == "complete"
        release.set()
        assert first.result() == "interrupted"
    assert repo.ai_usage("one", now=1202)["used"] == 2
    assert send(repo, now=1203) == "daily_limit"


def test_admission_insert_and_topic_changes_roll_back_together(repo):
    a = repo.create_topic("one", "原主题", now=1000)
    del a
    first = repo.active_topic("one")["topic_id"]
    repo.create_topic("one", "当前主题", now=1001)
    with closing(repo._connect()) as db, db:
        db.execute(
            "CREATE TRIGGER reject_usage BEFORE INSERT ON coach_ai_usage BEGIN SELECT RAISE(ABORT,'forced test rollback'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        repo.claim(
            "one",
            secrets.token_urlsafe(32),
            "不能半写入",
            now=1002,
            study_id=first,
            ai_kind="dialogue",
        )
    assert repo.active_topic("one")["title"] == "当前主题"
    assert (
        repo.view("one", now=1003)["turns"] == []
        and repo.ai_usage("one", now=1003)["used"] == 0
    )


def test_midnight_is_beijing_time_and_old_records_are_not_deleted(repo):
    limits(repo, user=1)
    midnight = int(datetime(2026, 10, 20, tzinfo=ZONE).timestamp())
    assert send(repo, now=midnight - 1) == "complete"
    assert send(repo, now=midnight - 1) == "daily_limit"
    assert send(repo, now=midnight) == "complete"
    current = repo.ai_usage("one", now=midnight)
    assert (
        current["day"] == "2026-10-20"
        and current["used"] == 1
        and current["retry_after"] == 86400
    )
    assert len(repo.conversation_records("one")) == 2


def test_recent_usage_is_owned_read_only_and_limited_to_seven_calendar_days(repo):
    today = datetime(2026, 10, 20, tzinfo=ZONE)
    for index in range(9):
        send(repo, now=int((today - timedelta(days=index)).timestamp()))
    send(repo, user="other", now=int(today.timestamp()))
    before = repo.database_path.read_bytes()
    snapshot = repo.ai_usage("one", now=int(today.timestamp()))
    assert (
        len(snapshot["recent"]) == 7
        and sum(row["count"] for row in snapshot["recent"]) == 7
    )
    assert snapshot["used"] == 1 and repo.database_path.read_bytes() == before


@pytest.mark.parametrize(
    "user,total",
    [(True, 1), (-1, 2), (10001, 10002), (1, -1), (1, 1000001), (3, 2), (None, 10)],
)
def test_invalid_limits_are_rejected(user, total):
    with pytest.raises(ValueError):
        validate_limits(user, total)


def test_backup_restores_usage_and_limits_without_refunding_attempts(space, tmp_path):
    root, user, *_ = space
    repo = CoachRepository(root / "coach_conversations.db")
    limits(repo, user=1, total=4)
    assert send(repo, user=user.user_id) == "complete"
    archive = backups.backup.create_backup(root, tmp_path / "usage.zip")
    target = tmp_path / "restored"
    backups.backup.restore_backup(archive, target)
    restored = CoachRepository(target / "coach_conversations.db")
    assert restored.ai_usage(user.user_id, now=1000)["used"] == 1
    assert restored.ai_usage(user.user_id, now=1000)["user_limit"] == 1
    assert send(restored, user=user.user_id) == "daily_limit"
