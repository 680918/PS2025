import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from zipfile import ZipFile

import pytest

from api.asset_export import build_export, booklet_document
from coach.booklets import booklet_markdown
from conversation.coach_repository import CoachRepository
from tests import test_booklets as base

records = base.records


def prepared(records):
    repo, _, _ = records
    first = repo.list_knowledge("one")[0]["knowledge_id"]
    second = base.lesson(repo, "续读章节")
    book = base.create(repo)
    for lesson in (first, second):
        base.change(repo, book, "add", lesson=lesson)
    return repo, book, first, second


def remember(repo, book, lesson, *, version=None, directory_version=None, user="one"):
    saved = repo.booklet(user, book, chapter=0)
    return repo.remember_booklet_position(
        user,
        book,
        saved["revision"] if directory_version is None else directory_version,
        lesson,
        saved["reading_position"]["revision"] if version is None else version,
    )


def test_position_is_explicit_durable_and_follows_lesson_after_order_and_revision(
    records,
):
    repo, book, first, second = prepared(records)
    before = repo.view("one")
    assert repo.booklet("one", book, chapter="resume")["selected_chapter"] == 1
    repo.booklet("one", book, chapter=2)
    assert repo.booklet("one", book)["reading_position"]["revision"] == 0
    assert remember(repo, book, second) == "saved"
    assert remember(repo, book, second, version=0) == "unchanged"
    selected = CoachRepository(repo.database_path).booklet(
        "one", book, chapter="resume"
    )
    assert selected["selected_chapter"] == 2
    assert selected["chapters"][0]["content"] is None
    base.change(repo, book, "up", lesson=second)
    repo.revise_knowledge(
        "one", second, 1, title="修订续读章节", content="当前版内容。"
    )
    selected = repo.booklet("one", book, chapter="resume")
    assert selected["selected_chapter"] == 1
    assert selected["chapters"][0]["content"] == "当前版内容。"
    assert selected["chapters"][0]["revision"] == 2
    assert repo.list_booklets("one")[0]["reading_position"]["number"] == 1
    assert repo.view("one") == before
    assert repo.booklet("one", book, chapter=2)["selected_chapter"] == 2
    assert repo.booklet("one", book)["reading_position"]["knowledge_id"] == second


def test_bookmarks_are_independent_between_books_and_users(records):
    repo, book, first, second = prepared(records)
    another = base.create(repo, "另一本")
    base.change(repo, another, "add", lesson=first)
    remember(repo, book, second)
    remember(repo, another, first)
    assert repo.booklet("one", book)["reading_position"]["knowledge_id"] == second
    assert repo.booklet("one", another)["reading_position"]["knowledge_id"] == first
    assert repo.remember_booklet_position("two", book, 3, first, 0) == "missing"
    assert repo.list_booklets("two") == []


def test_removed_or_unavailable_position_is_honest_and_can_be_replaced(records):
    repo, book, first, second = prepared(records)
    remember(repo, book, second)
    base.change(repo, book, "remove", lesson=second)
    selected = repo.booklet("one", book, chapter="resume")
    assert selected["selected_chapter"] == 1
    assert selected["reading_position"]["number"] is None
    assert "已移出或暂不可用" in booklet_markdown(selected)
    assert repo.knowledge("one", second, saved_only=True)
    base.change(repo, book, "add", lesson=second)
    assert repo.booklet("one", book, chapter="resume")["selected_chapter"] == 2
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "UPDATE coach_knowledge SET status='pending' WHERE knowledge_id=?",
            (second,),
        )
    assert repo.booklet("one", book)["reading_position"]["number"] is None
    with pytest.raises(ValueError, match="本手册"):
        remember(repo, book, second)
    assert remember(repo, book, first) == "saved"
    assert repo.booklet("one", book)["reading_position"]["revision"] == 2


def test_concurrent_positions_and_changed_directory_do_not_overwrite(records):
    repo, book, first, second = prepared(records)

    def save(lesson):
        return repo.remember_booklet_position("one", book, 3, lesson, 0)

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(save, (first, second))) == ["conflict", "saved"]
    existing = repo.booklet("one", book)["reading_position"]
    other = second if existing["knowledge_id"] == first else first
    assert remember(repo, book, other, version=0) == "conflict"
    base.change(repo, book, "title", title="新目录名称")
    assert remember(repo, book, other, directory_version=3) == "conflict"
    assert repo.booklet("one", book)["reading_position"] == existing


def test_membership_guard_and_transaction_rollback(records):
    repo, book, first, second = prepared(records)
    foreign = repo.list_knowledge("two", status="pending")[0]["knowledge_id"]
    unrelated = base.lesson(repo, "未收录")
    for invalid in (foreign, unrelated, uuid4().hex):
        with pytest.raises(ValueError):
            remember(repo, book, invalid)
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER fail_position BEFORE INSERT ON coach_booklet_positions BEGIN SELECT RAISE(ABORT,'test'); END"
        )
    with pytest.raises(sqlite3.Error):
        remember(repo, book, second)
    assert repo.booklet("one", book)["reading_position"]["revision"] == 0
    assert repo.booklet("one", book)["revision"] == 3


def test_current_position_export_is_owned_safe_and_compatible_with_old_database(
    records, tmp_path
):
    repo, book, first, second = prepared(records)
    remember(repo, book, second)
    snapshot = repo.booklet("one", book)
    assert "已记到第 2 章" in booklet_markdown(snapshot)
    assert "已记到第 2 章" in booklet_document(snapshot)
    materials = records[1]
    bundle = build_export(
        repo.database_path,
        materials.database_path,
        "one",
        ["booklets"],
        period="all",
    )
    try:
        with ZipFile(bundle.file) as archive:
            for name in archive.namelist():
                if name.startswith("学习手册/") and name.endswith((".md", ".html")):
                    assert "已记到第 2 章" in archive.read(name).decode("utf-8")
    finally:
        bundle.close()
    with sqlite3.connect(repo.database_path) as db:
        db.execute("DROP TABLE coach_booklet_positions")
    from coach.booklets import booklet_snapshot

    with sqlite3.connect(repo.database_path) as db:
        db.row_factory = sqlite3.Row
        old = booklet_snapshot(db, "one", book)
        assert old["reading_position"]["revision"] == 0
        assert "尚未记住" in booklet_markdown(old)
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='coach_booklet_positions'"
            ).fetchone()
            is None
        )


@pytest.mark.parametrize(
    "revision,position_revision,lesson",
    [
        (0, 0, "a" * 32),
        (1, -1, "a" * 32),
        (True, 0, "a" * 32),
        (1, False, "a" * 32),
        (1, 0, "bad"),
    ],
)
def test_invalid_position_values_are_rejected(
    records, revision, position_revision, lesson
):
    repo, book, _, _ = prepared(records)
    with pytest.raises(ValueError):
        repo.remember_booklet_position("one", book, revision, lesson, position_revision)


def test_corrupted_foreign_bookmark_does_not_disclose_foreign_title(records):
    repo, book, _, _ = prepared(records)
    foreign = repo.list_knowledge("two", status="pending")[0]["knowledge_id"]
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "INSERT INTO coach_booklet_positions VALUES('one',?,?,1,1000)",
            (book, foreign),
        )
    current = repo.booklet("one", book, chapter="resume")
    assert current["reading_position"]["number"] is None
    exported = repo.booklet("one", book)
    assert "他人草稿" not in booklet_markdown(exported)
