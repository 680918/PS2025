import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from uuid import uuid4

import pytest

from coach.draft_edit import draft_version
from conversation.coach_repository import CoachRepository
from tests.test_lesson_revision import saved_lesson


def seed(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    identity = saved_lesson(repo)
    return repo, identity


def test_favorite_is_a_persistent_shortcut_without_content_learning_or_usage_changes(
    tmp_path,
):
    repo, identity = seed(tmp_path)
    before = repo.knowledge("one", identity)
    view, usage = repo.view("one", now=1002), repo.ai_usage("one", now=1002)
    raw = repo.database_path.read_bytes()
    assert repo.lesson_favorite("one", identity) == {"selected": False, "revision": 0}
    assert repo.list_knowledge("one", favorites_only=True) == []
    assert repo.database_path.read_bytes() == raw
    assert repo.set_lesson_favorite("one", identity, True, 0) == "updated"
    restarted = CoachRepository(repo.database_path)
    assert restarted.lesson_favorite("one", identity) == {
        "selected": True,
        "revision": 1,
    }
    assert restarted.list_knowledge(
        "one", favorites_only=True
    ) == restarted.list_knowledge("one")
    assert restarted.knowledge("one", identity) == before
    assert (
        restarted.view("one", now=1002) == view
        and restarted.ai_usage("one", now=1002) == usage
    )
    assert restarted.set_lesson_favorite("one", identity, False, 1) == "updated"
    assert restarted.list_knowledge("one", favorites_only=True) == []
    assert restarted.knowledge("one", identity) == before


def test_owner_and_saved_state_are_required_and_noop_does_not_write(tmp_path):
    repo, identity = seed(tmp_path)
    pending = saved_lesson(repo, save=False)
    dismissed = saved_lesson(repo, user="two", save=False)
    repo.confirm_knowledge("two", dismissed, save=False)
    raw = repo.database_path.read_bytes()
    for user, target in [
        ("two", identity),
        ("one", pending),
        ("two", dismissed),
        ("one", "missing"),
    ]:
        assert repo.lesson_favorite(user, target) is None
        assert repo.set_lesson_favorite(user, target, True, 0) == "missing"
    assert repo.set_lesson_favorite("one", identity, False, 0) == "unchanged"
    assert repo.database_path.read_bytes() == raw
    assert repo.set_lesson_favorite("one", identity, True, 0) == "updated"
    raw = repo.database_path.read_bytes()
    assert repo.set_lesson_favorite("one", identity, True, 1) == "unchanged"
    assert repo.database_path.read_bytes() == raw


def test_stale_forms_and_repeated_cycles_cannot_reverse_a_newer_choice(tmp_path):
    repo, identity = seed(tmp_path)
    assert repo.set_lesson_favorite("one", identity, True, 0) == "updated"
    assert repo.set_lesson_favorite("one", identity, False, 1) == "updated"
    assert repo.set_lesson_favorite("one", identity, True, 0) == "conflict"
    assert repo.set_lesson_favorite("one", identity, True, 2) == "updated"
    assert repo.set_lesson_favorite("one", identity, False, 1) == "conflict"
    assert repo.lesson_favorite("one", identity) == {"selected": True, "revision": 3}


def test_concurrent_favorite_has_one_winner_and_failure_rolls_back(tmp_path):
    repo, identity = seed(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: repo.set_lesson_favorite("one", identity, True, 0), range(2)
            )
        )
    assert sorted(results) == ["conflict", "updated"]
    with closing(repo._connect()) as db, db:
        db.execute(
            "CREATE TRIGGER stop_favorite BEFORE UPDATE ON coach_lesson_favorites BEGIN SELECT RAISE(ABORT,'test failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        repo.set_lesson_favorite("one", identity, False, 1)
    assert repo.lesson_favorite("one", identity) == {"selected": True, "revision": 1}


def test_favorite_tracks_current_revisions_without_duplicate_lessons_or_booklet_changes(
    tmp_path,
):
    repo, identity = seed(tmp_path)
    book = uuid4().hex
    repo.create_booklet("one", book, "我的手册")
    repo.change_booklet("one", book, 1, "add", knowledge_id=identity)
    before = repo.booklet("one", book, chapter=0)
    repo.set_lesson_favorite("one", identity, True, 0)
    assert repo.booklet("one", book, chapter=0) == before
    assert (
        repo.revise_knowledge(
            "one", identity, 1, title="当前标题", content="新的可查找正文"
        )
        == "updated"
    )
    found = repo.list_knowledge("one", favorites_only=True, query="可查找")
    assert len(found) == 1 and found[0]["title"] == "当前标题"
    assert repo.knowledge("one", identity)["revision"] == 2
    assert repo.revise_knowledge("one", identity, 2, restore=1) == "updated"
    assert repo.lesson_favorite("one", identity) == {"selected": True, "revision": 1}
    assert len(repo.list_knowledge("one")) == 1
    assert repo.list_knowledge("one", favorites_only=True, query="可查找") == []


def test_historical_database_migration_and_saved_filter_even_if_stale_metadata_exists(
    tmp_path,
):
    repo, identity = seed(tmp_path)
    with closing(repo._connect()) as db, db:
        db.execute("DROP TABLE coach_lesson_favorites")
    restarted = CoachRepository(repo.database_path)
    assert restarted.lesson_favorite("one", identity) == {
        "selected": False,
        "revision": 0,
    }
    assert restarted.set_lesson_favorite("one", identity, True, 0) == "updated"
    with closing(repo._connect()) as db, db:
        db.execute(
            "UPDATE coach_knowledge SET status='pending' WHERE knowledge_id=?",
            (identity,),
        )
    assert restarted.list_knowledge("one", status="pending", favorites_only=True) == []
    assert restarted.lesson_favorite("one", identity) is None
    # Pending draft actions continue to use their independent content version.
    item = restarted.knowledge("one", identity)
    assert (
        restarted.change_draft(
            "one", identity, "stage", draft_version(item), title="草稿", content="内容"
        )
        == "staged"
    )


@pytest.mark.parametrize(
    "selected,revision",
    [(1, 0), ("1", 0), (True, True), (True, -1), (False, 1000000001), (True, "1")],
)
def test_invalid_state_or_revision_is_rejected_without_writes(
    tmp_path, selected, revision
):
    repo, identity = seed(tmp_path)
    raw = repo.database_path.read_bytes()
    with pytest.raises(ValueError):
        repo.set_lesson_favorite("one", identity, selected, revision)
    assert repo.database_path.read_bytes() == raw
