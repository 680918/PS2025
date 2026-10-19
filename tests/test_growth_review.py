from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from conversation.coach_repository import CoachRepository
from tests.test_conversation_review import turn, topic
from tests.test_lesson_revision import saved_lesson

ZONE = timezone(timedelta(hours=8))
NOW = int(datetime(2026, 10, 19, 0, 30, tzinfo=ZONE).timestamp())
START = int(datetime(2026, 10, 13, tzinfo=ZONE).timestamp())


def lesson(repo, user="one", *, title="确认的教案", saved_at=NOW, save=True):
    identity = saved_lesson(repo, user=user, title=title, save=save)
    if save:
        with closing(repo._connect()) as db, db:
            db.execute(
                "UPDATE coach_knowledge SET saved_at=? WHERE knowledge_id=?",
                (saved_at, identity),
            )
    return identity


def test_inclusive_beijing_calendar_window_uses_completion_and_first_confirmation(
    tmp_path,
):
    repo = CoachRepository(tmp_path / "coach.db")
    a = topic(repo, "学习方法")
    old = turn(repo, "起点前完成", now=START - 2)
    boundary = turn(repo, "起点恰好完成", now=START - 1)
    today = turn(repo, "今天已完成", now=NOW - 1)
    future = turn(repo, "未来完成不可计算", now=NOW)
    turn(repo, "失败不计算", now=NOW - 20, status="failed")
    first = lesson(repo, saved_at=START)
    lesson(repo, title="窗口外教案", saved_at=START - 1)
    lesson(repo, title="未来教案", saved_at=NOW + 1)
    repo.revise_knowledge(
        "one", first, 1, title="当前新版标题", content="更新正文", now=NOW
    )
    snapshot = repo.growth_review("one", now=NOW)
    assert snapshot["start_day"] == "2026-10-13" and snapshot["end_day"] == "2026-10-19"
    assert (
        snapshot["completed_turns"] == 2
        and snapshot["saved_lessons"] == 1
        and snapshot["active_topics"] == 1
    )
    assert {row["turn_id"] for row in snapshot["recent_turns"]} == {boundary, today}
    assert old not in {
        row["turn_id"] for row in snapshot["recent_turns"]
    } and future not in {row["turn_id"] for row in snapshot["recent_turns"]}
    assert snapshot["recent_lessons"][0]["title"] == "当前新版标题"
    assert snapshot["recent_topics"][0]["topic_id"] == a
    assert snapshot["recent_topics"][0]["completed_turns"] == 2


def test_thirty_day_and_all_periods_keep_unfiled_records_and_do_not_guess_topics(
    tmp_path,
):
    repo = CoachRepository(tmp_path / "coach.db")
    old = turn(repo, "更早的未分类记录", now=NOW - 40 * 86400)
    unfiled = turn(repo, "窗口内未分类记录", now=NOW - 20 * 86400)
    active = topic(repo, "现有主题")
    turn(repo, "本周已讨论", now=NOW - 10)
    empty = topic(repo, "没有完成对话的新主题")
    snapshot = repo.growth_review("one", period="30", now=NOW)
    assert snapshot["start_day"] == "2026-09-20"
    assert (
        snapshot["completed_turns"] == 2
        and snapshot["active_topics"] == 1
        and snapshot["unfiled_turns"] == 1
    )
    assert {r["turn_id"] for r in snapshot["recent_turns"]} >= {unfiled}
    assert snapshot["recent_topics"][0]["topic_id"] == active
    assert empty not in {r["topic_id"] for r in snapshot["recent_topics"]}
    all_time = repo.growth_review("one", period="all", now=NOW)
    assert all_time["start_day"] is None and all_time["completed_turns"] == 3
    assert old in {r["turn_id"] for r in all_time["recent_turns"]}


def test_owner_scope_pending_dismissed_and_unfinished_records_are_excluded(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    other_topic = topic(repo, "其他人的主题", user="two")
    turn(repo, "其他人的问题", user="two", now=NOW - 1)
    lesson(repo, user="two", saved_at=NOW)
    draft = lesson(repo, save=False)
    repo.confirm_knowledge("one", draft, save=False)
    pending = lesson(repo, save=False)
    turn(repo, "未完成", now=NOW - 1, status="pending")
    before = repo.database_path.read_bytes()
    snapshot = repo.growth_review("one", period="all", now=NOW)
    # The two draft-generation exchanges completed, but neither draft is confirmed.
    assert snapshot["completed_turns"] == 2 and snapshot["saved_lessons"] == 0
    assert snapshot["active_topics"] == 0 and snapshot["recent_lessons"] == []
    assert other_topic not in str(snapshot) and "其他人的" not in str(snapshot)
    assert repo.knowledge("one", pending)["status"] == "pending"
    assert repo.database_path.read_bytes() == before


def test_only_reading_is_repeatable_across_restart_and_lists_are_bounded(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    for number in range(8):
        topic(repo, f"主题{number}")
        turn(repo, "长问题" + "字" * 300, now=NOW - 100 + number)
        lesson(repo, title=f"教案{number}", saved_at=NOW - 100 + number)
    before = repo.database_path.read_bytes()
    snapshot = repo.growth_review("one", now=NOW)
    assert (
        snapshot["completed_turns"] == 8
        and snapshot["active_topics"] == 8
        and snapshot["saved_lessons"] == 8
    )
    assert all(
        len(snapshot[name]) == 5
        for name in ["recent_turns", "recent_lessons", "recent_topics"]
    )
    assert all(
        len(row["question"]) == 180 and row["shortened"]
        for row in snapshot["recent_turns"]
    )
    assert repo.database_path.read_bytes() == before
    assert CoachRepository(repo.database_path).growth_review("one", now=NOW) == snapshot


def test_counts_by_completed_time_and_empty_account_stays_empty(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    identity = turn(repo, "旧时发起但本期才完成", now=START - 1000)
    with closing(repo._connect()) as db, db:
        db.execute(
            "UPDATE coach_turns SET completed_at=? WHERE turn_id=?", (START, identity)
        )
    assert repo.growth_review("one", now=NOW)["completed_turns"] == 1
    empty = repo.growth_review("new", now=NOW)
    assert (
        empty["completed_turns"]
        == empty["saved_lessons"]
        == empty["active_topics"]
        == 0
    )
    assert (
        empty["recent_turns"] == empty["recent_lessons"] == empty["recent_topics"] == []
    )


@pytest.mark.parametrize("period", ["", 7, 30, None, "90", "7 OR 1=1"])
def test_invalid_periods_do_not_write(tmp_path, period):
    repo = CoachRepository(tmp_path / "coach.db")
    before = repo.database_path.read_bytes()
    with pytest.raises(ValueError):
        repo.growth_review("one", period=period, now=NOW)
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize("now", [-1, True, "2026-10-19", 1.5])
def test_invalid_clock_is_rejected(tmp_path, now):
    repo = CoachRepository(tmp_path / "coach.db")
    with pytest.raises(ValueError):
        repo.growth_review("one", now=now)


def test_summary_and_lists_share_one_snapshot_during_a_concurrent_completion(
    tmp_path, monkeypatch
):
    repo = CoachRepository(tmp_path / "coach.db")
    turn(repo, "先完成的对话", now=NOW - 10)
    connect = repo._connect
    with closing(connect()) as db:
        db.execute("PRAGMA journal_mode=WAL")
    inserted = []

    class ConcurrentConnection:
        def __init__(self):
            self.db = connect()

        def close(self):
            self.db.close()

        def execute(self, sql, parameters=()):
            cursor = self.db.execute(sql, parameters)
            if sql.startswith("SELECT COUNT(*) AS completed_turns") and not inserted:
                with closing(connect()) as writer, writer:
                    writer.execute(
                        "INSERT INTO coach_turns(user_id,nonce,user_content,assistant_content,status,created_at,completed_at) VALUES(?,?,?,?,?,?,?)",
                        (
                            "one",
                            "concurrent-test",
                            "读取过程中刚完成的对话",
                            "回复",
                            "complete",
                            NOW - 2,
                            NOW - 1,
                        ),
                    )
                inserted.append(True)
            return cursor

    monkeypatch.setattr(repo, "_connect", ConcurrentConnection)
    snapshot = repo.growth_review("one", now=NOW)
    assert (
        inserted
        and snapshot["completed_turns"] == 1
        and len(snapshot["recent_turns"]) == 1
    )
    assert repo.growth_review("one", now=NOW)["completed_turns"] == 2
