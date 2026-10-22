from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from coach.materials import MaterialError, MaterialRepository


def book(tmp_path):
    repo = MaterialRepository(tmp_path / "books.db")
    identity = repo.add("one", "book.txt", ("学习原文与阅读位置。" * 1400).encode())
    return repo, identity


def test_position_is_owned_idempotent_and_survives_repository_reopen(tmp_path):
    repo, identity = book(tmp_path)
    original = repo.original("one", identity)
    assert repo.reading_position("one", identity) == {"page": 1, "revision": 0}
    assert repo.reading_position("two", identity) is None
    assert repo.save_reading_position("two", identity, 2, 0) == {"status": "missing"}
    assert repo.save_reading_position("one", identity, 2, 0) == {
        "status": "saved",
        "page": 2,
        "revision": 1,
    }
    before = repo.database_path.read_bytes()
    assert repo.save_reading_position("one", identity, 2, 0)["revision"] == 1
    assert repo.database_path.read_bytes() == before
    restored = MaterialRepository(repo.database_path)
    assert restored.reading_position("one", identity) == {"page": 2, "revision": 1}
    assert restored.original("one", identity) == original


def test_stale_tab_cannot_overwrite_a_newer_page(tmp_path):
    repo, identity = book(tmp_path)
    repo.save_reading_position("one", identity, 2, 0)
    repo.save_reading_position("one", identity, 3, 1)
    before = repo.database_path.read_bytes()
    assert repo.save_reading_position("one", identity, 1, 0) == {
        "status": "conflict",
        "page": 3,
        "revision": 2,
    }
    assert repo.database_path.read_bytes() == before
    assert repo.save_reading_position("one", identity, 1, 2)["revision"] == 3


def test_two_concurrent_windows_have_one_winner(tmp_path):
    repo, identity = book(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda n: repo.save_reading_position("one", identity, n, 0), (2, 3)
            )
        )
    assert sorted(r["status"] for r in results) == ["conflict", "saved"]
    assert repo.reading_position("one", identity)["revision"] == 1


@pytest.mark.parametrize(
    "page, revision",
    [(0, 0), (1501, 0), (True, 0), (2, True), (2, -1), (2, 1000000000), (100, 0)],
)
def test_bad_or_out_of_book_position_does_not_write(tmp_path, page, revision):
    repo, identity = book(tmp_path)
    before = repo.database_path.read_bytes()
    with pytest.raises(MaterialError):
        repo.save_reading_position("one", identity, page, revision)
    assert repo.database_path.read_bytes() == before


def test_old_database_adds_position_table_without_rewriting_book(tmp_path):
    repo, identity = book(tmp_path)
    content = repo.original("one", identity)
    with sqlite3.connect(repo.database_path) as db:
        db.execute("DROP TABLE material_reading_positions")
    upgraded = MaterialRepository(repo.database_path)
    assert upgraded.original("one", identity) == content
    assert upgraded.reading_position("one", identity)["revision"] == 0
