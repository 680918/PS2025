import sqlite3

import pytest

from coach.materials import MaterialError, MaterialRepository
from tests.test_web_book_reader import image_book
from tests.test_coach_materials import pdf_bytes


def test_coverage_counts_pages_not_chunks_and_preserves_original_and_bookmark(tmp_path):
    repo = MaterialRepository(tmp_path / "books.db")
    raw = image_book()
    identity = repo.add("one", "scan.pdf", raw)
    native = repo.chunks("one", identity)[0]
    for number in (5, 1):
        digest = repo.ocr_page("one", identity, number)["digest"]
        assert (
            repo.save_ocr_page(
                "one", identity, number, "核对后的原文。" * 300, 90, digest
            )
            == "saved"
        )
    repo.save_reading_position("one", identity, 8, 0)
    before = repo.database_path.read_bytes()
    coverage = repo.text_coverage("one", identity)
    assert {key: value for key, value in coverage.items() if key != "pages"} == {
        "total": 12,
        "native": 1,
        "confirmed": 2,
        "missing": 9,
    }
    assert coverage["pages"] == [
        {
            "page": page,
            "state": "confirmed"
            if page in {1, 5}
            else "native"
            if page == 12
            else "missing",
        }
        for page in range(1, 13)
    ]
    assert repo.database_path.read_bytes() == before
    restarted = MaterialRepository(repo.database_path)
    assert restarted.text_coverage("one", identity) == coverage
    assert restarted.reading_position("one", identity)["page"] == 8
    assert restarted.original("one", identity)["content"] == raw
    kept = restarted.chunk("one", identity, native["chunk_id"])
    assert (kept["locator"], kept["content"]) == (native["locator"], native["content"])
    assert "核对后的原文" not in repr(coverage) and "digest" not in coverage


def test_other_users_text_materials_and_missing_books_do_not_expose_coverage(tmp_path):
    repo = MaterialRepository(tmp_path / "books.db")
    identity = repo.add("one", "scan.pdf", image_book(3))
    text = repo.add("one", "text.txt", "私有文字。".encode())
    before = repo.database_path.read_bytes()
    assert repo.text_coverage("two", identity) is None
    assert repo.text_coverage("one", text) is None
    assert repo.text_coverage("one", "missing") is None
    assert repo.database_path.read_bytes() == before


def test_empty_page_is_missing_until_explicit_approval(tmp_path):
    repo = MaterialRepository(tmp_path / "books.db")
    identity = repo.add("one", "empty.pdf", pdf_bytes(blank=True))
    before = repo.text_coverage("one", identity)
    assert before["pages"] == [{"page": 1, "state": "missing"}]
    assert (
        repo.save_ocr_page(
            "one",
            identity,
            1,
            "用户明确核对的文字。",
            90,
            repo.ocr_page("one", identity, 1)["digest"],
        )
        == "saved"
    )
    current = repo.text_coverage("one", identity)
    assert current["missing"] == current["native"] == 0 and current["confirmed"] == 1
    assert current["pages"] == [{"page": 1, "state": "confirmed"}]
    assert before["pages"][0]["state"] == "missing"


@pytest.mark.parametrize("mutation", ["locator", "outside", "orphan_approval"])
def test_unverifiable_page_records_fail_without_writes(tmp_path, mutation):
    repo = MaterialRepository(tmp_path / "books.db")
    identity = repo.add("one", "scan.pdf", image_book(3))
    with sqlite3.connect(repo.database_path) as db:
        if mutation == "locator":
            db.execute(
                "UPDATE material_chunks SET locator='unknown' WHERE material_id=?",
                (identity,),
            )
        elif mutation == "outside":
            db.execute(
                "UPDATE material_chunks SET locator='PDF 第 4 页 · 片段 1' WHERE material_id=?",
                (identity,),
            )
        else:
            db.execute(
                "INSERT INTO material_ocr_pages VALUES(?,1,90,'fixture',1)", (identity,)
            )
    before = repo.database_path.read_bytes()
    with pytest.raises(MaterialError):
        repo.text_coverage("one", identity)
    assert repo.database_path.read_bytes() == before
