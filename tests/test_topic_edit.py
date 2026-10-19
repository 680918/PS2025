import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from coach.learning_topics import TopicBusy, topic_edit_version
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository


def topic(repo, user="one", title="阅读方法", now=100):
    repo.create_topic(user, title, now=now)
    return repo.active_topic(user)


def edit(
    repo,
    row,
    *,
    title="我的阅读学习",
    progress="讨论了回想。",
    next_step="用一个例子应用。",
    now=110,
):
    return repo.edit_topic(
        row["user_id"],
        row["topic_id"],
        title,
        progress,
        next_step,
        expected_version=topic_edit_version(row),
        now=now,
    )


def test_current_edit_is_atomic_persistent_and_keeps_book_part_history_and_usage(
    tmp_path,
):
    materials = MaterialRepository(tmp_path / "materials.db")
    book = materials.add("one", "book.txt", ("先回想再实践。" * 160).encode())
    repo = CoachRepository(tmp_path / "coach.db", materials=materials)
    topic(repo)
    chunk = materials.chunks("one", book)[1]
    repo.select_material_part("one", book, "原书", chunk["chunk_id"], now=101)
    row = repo.active_topic("one")
    repo.save_book_unit("one", book, "a" * 32, "第一单元", 1, 2, 0, now=102)
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "原始问题", now=103, ai_kind="dialogue")
    repo.finish(
        "one",
        nonce,
        "原始回复",
        None,
        now=104,
        citations=[
            {
                "source_id": chunk["chunk_id"],
                "material_id": book,
                "title": "原书",
                "locator": chunk["locator"],
                "excerpt": chunk["content"],
            }
        ],
        draft={"title": "旧教案", "topic": "阅读方法", "content": "原教案"},
    )
    part, units, view, usage = (
        repo.topic_part("one"),
        repo.book_units("one", book),
        repo.view("one", now=105),
        repo.ai_usage("one", now=105),
    )
    assert edit(repo, row) == "updated"
    restarted = CoachRepository(repo.database_path, materials=materials)
    current = restarted.active_topic("one")
    assert current["topic_id"] == row["topic_id"] and current["material_id"] == book
    assert (
        current["title"] == "我的阅读学习"
        and current["created_at"] == row["created_at"]
    )
    assert restarted.view("one", now=111)["learning"] == {
        "topic": "我的阅读学习",
        "progress": "讨论了回想。",
        "next_step": "用一个例子应用。",
        "updated_at": 110,
    }
    assert restarted.view("one", now=111)["turns"] == view["turns"]
    assert (
        restarted.topic_part("one") == part
        and restarted.book_units("one", book) == units
    )
    assert restarted.list_knowledge("one", status="pending")[0]["title"] == "旧教案"
    assert restarted.ai_usage("one", now=105) == usage
    assert materials.get("one", book)["filename"] == "book.txt"


def test_inactive_edit_does_not_switch_current_or_rewrite_legacy_anchor(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    first = topic(repo)
    other = topic(repo, title="沟通方法", now=101)
    before = repo.view("one", now=102)
    assert edit(repo, first) == "updated"
    assert repo.active_topic("one") == other
    assert repo.view("one", now=111) == before
    assert (
        repo.list_topics("one", query="我的阅读学习")[0]["topic_id"]
        == first["topic_id"]
    )


def test_stale_editor_detects_ai_change_in_same_second_and_does_not_write(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    row = topic(repo)
    with closing(repo._connect()) as db, db:
        db.execute(
            "UPDATE coach_topics SET progress=? WHERE topic_id=?",
            ("新一轮已经讨论的内容", row["topic_id"]),
        )
    current = repo.topic("one", row["topic_id"])
    assert current["updated_at"] == row["updated_at"]
    assert edit(repo, row) == "conflict"
    assert repo.topic("one", row["topic_id"]) == current
    assert edit(repo, current) == "updated"


def test_ownership_noop_busy_and_normalized_duplicate_name(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    row = topic(repo)
    topic(repo, title="Python 入门", now=101)
    assert edit(repo, row, title="Ｐｙｔｈｏｎ　入门") == "duplicate"
    assert (
        repo.edit_topic(
            "other",
            row["topic_id"],
            "私有修改",
            "x",
            "y",
            expected_version=topic_edit_version(row),
        )
        == "missing"
    )
    own = repo.topic("one", row["topic_id"])
    assert (
        edit(
            repo,
            own,
            title=own["title"],
            progress=own["progress"],
            next_step=own["next_step"],
        )
        == "unchanged"
    )
    assert repo.topic("one", row["topic_id"]) == own
    repo.claim("one", secrets.token_urlsafe(32), "还在回复", now=109)
    with pytest.raises(TopicBusy):
        edit(repo, own)
    assert repo.topic("one", row["topic_id"]) == own


@pytest.mark.parametrize(
    "values",
    [
        ("", "x", "y"),
        ("字" * 121, "x", "y"),
        ("bad\nname", "x", "y"),
        ("name", "", "y"),
        ("name", "x", "字" * 801),
        ("name", "x\x00", "y"),
        ("name", "x", "\ud800"),
        (None, "x", "y"),
    ],
)
def test_invalid_fields_never_change_topic(tmp_path, values):
    repo = CoachRepository(tmp_path / "coach.db")
    row = topic(repo)
    with pytest.raises(ValueError):
        repo.edit_topic(
            "one", row["topic_id"], *values, expected_version=topic_edit_version(row)
        )
    assert repo.active_topic("one") == row


def test_concurrent_editors_have_one_winner(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    row = topic(repo)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda title: edit(repo, row, title=title), ["First", "Second"])
        )
    assert sorted(results) == ["conflict", "updated"]
    assert repo.active_topic("one")["title"] in {"First", "Second"}


def test_failure_syncing_active_anchor_rolls_back_entire_edit(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    row = topic(repo)
    with closing(repo._connect()) as db, db:
        db.execute(
            "CREATE TRIGGER fail_edit BEFORE UPDATE ON coach_learning BEGIN SELECT RAISE(ABORT,'test failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        edit(repo, row)
    assert repo.active_topic("one") == row
    assert repo.view("one", now=111)["learning"]["topic"] == row["title"]
