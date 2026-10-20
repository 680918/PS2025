from datetime import datetime, timezone

import pytest

from coach.conversation_dates import conversation_date_window
from conversation.coach_repository import CoachRepository
from tests.test_conversation_review import turn, topic


def test_beijing_midnight_leap_day_and_inclusive_end():
    lower, upper = conversation_date_window("2024-02-29", "2024-02-29")
    assert lower == int(datetime(2024, 2, 28, 16, tzinfo=timezone.utc).timestamp())
    assert upper - lower == 86400
    assert conversation_date_window("2024-02-29", "") == (lower, None)
    assert conversation_date_window("", "2024-02-29") == (None, upper)
    assert conversation_date_window() == (None, None)
    assert conversation_date_window("0001-01-01", "9999-12-31")[1] > 0


@pytest.mark.parametrize(
    "start,end",
    [
        ("2023-02-29", ""),
        ("2024-13-01", ""),
        ("2024-2-01", ""),
        ("0000-01-01", ""),
        ("2024-03-01", "2024-02-29"),
        (None, ""),
        (True, ""),
        ("", "x"),
        (" 2024-01-01", ""),
        ("2024-01-01\n", ""),
        ("2024-01-01T00:00", ""),
    ],
)
def test_invalid_dates_are_rejected(start, end):
    with pytest.raises(ValueError):
        conversation_date_window(start, end)


@pytest.fixture
def repo(tmp_path):
    return CoachRepository(tmp_path / "dialogue.db")


def test_exact_date_boundaries_use_question_time_and_do_not_write(repo):
    lower, upper = conversation_date_window("2024-02-29", "2024-02-29")
    ids = [
        turn(repo, f"边界问题{n}", now=stamp)
        for n, stamp in enumerate([lower - 1, lower, upper - 1, upper])
    ]
    before = repo.database_path.read_bytes()
    records = repo.conversation_records(
        "one", start_day="2024-02-29", end_day="2024-02-29"
    )
    assert [x["turn_id"] for x in records] == [ids[2], ids[1]]
    assert [
        x["turn_id"] for x in repo.conversation_records("one", start_day="2024-02-29")
    ] == ids[:0:-1]
    assert [
        x["turn_id"] for x in repo.conversation_records("one", end_day="2024-02-29")
    ] == ids[2::-1]
    assert repo.database_path.read_bytes() == before
    assert (
        CoachRepository(repo.database_path).conversation_records(
            "one", start_day="2024-02-29", end_day="2024-02-29"
        )
        == records
    )


def test_dates_compose_with_literal_keyword_topic_and_account_scope(repo):
    lower, _ = conversation_date_window("2024-02-29", "")
    a = topic(repo, "日期主题")
    own = turn(repo, "按100%_核对", now=lower)
    turn(repo, "另一个问题", now=lower + 2)
    topic(repo, "其他主题", now=lower + 3)
    turn(repo, "按100%_核对", now=lower + 4)
    turn(repo, "按100%_核对", user="two", now=lower + 6)
    found = repo.conversation_records(
        "one", query="100%_", topic_id=a, start_day="2024-02-29", end_day="2024-02-29"
    )
    assert [x["turn_id"] for x in found] == [own]
    assert repo.conversation_records("two", topic_id=a, start_day="2024-02-29") == []


def test_pagination_and_pending_state_are_unchanged_by_date_read(repo):
    lower, _ = conversation_date_window("2024-02-29", "")
    ids = [turn(repo, "在日期范围内", now=lower + n * 2) for n in range(25)]
    pending = turn(repo, "仍在等待", now=lower + 100, status="pending")
    before = repo.database_path.read_bytes()
    first = repo.conversation_records(
        "one", start_day="2024-02-29", end_day="2024-02-29"
    )
    second = repo.conversation_records(
        "one", start_day="2024-02-29", end_day="2024-02-29", page=2
    )
    assert (
        len(first) == 21
        and first[0]["turn_id"] == pending
        and first[0]["status"] == "pending"
    )
    assert [x["turn_id"] for x in second] == ids[5::-1]
    assert repo.database_path.read_bytes() == before
