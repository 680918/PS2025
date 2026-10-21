import gzip
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from coach.materials import MaterialError, MaterialRepository
from conversation.coach_repository import CoachRepository
from tests.test_web_book_reader import image_book


def book(tmp_path):
    materials = MaterialRepository(tmp_path / "books.db")
    raw = image_book(12)
    identity = materials.add("one", "scan.pdf", raw)
    return materials, identity, raw


def save(
    materials,
    identity,
    number=1,
    text="先提问，再核对原文。",
    confidence=92,
    user="one",
    digest=None,
):
    return materials.save_ocr_page(
        user,
        identity,
        number,
        text,
        confidence,
        digest
        if digest is not None
        else materials.ocr_page("one", identity, 1)["digest"],
    )


def test_reviewed_ocr_preserves_original_and_existing_chunk_and_learning_identity(
    tmp_path,
):
    materials, identity, raw = book(tmp_path)
    original = materials.chunks("one", identity)[0]
    coach = CoachRepository(tmp_path / "coach.db", materials=materials)
    coach.select_material_part("one", identity, "扫描书", original["chunk_id"])
    topic = coach.active_topic("one")
    position = coach.topic_part("one")
    before = coach.database_path.read_bytes()
    assert materials.ocr_page("one", identity, 1)["state"] == "missing"
    assert (
        save(materials, identity, text="第一章：先提出问题，然后核对证据。" * 100)
        == "saved"
    )
    chunks = materials.chunks("one", identity)
    assert chunks[-1]["chunk_id"] == original["chunk_id"]
    assert (
        materials.chunk("one", identity, original["chunk_id"])["content"]
        == original["content"]
    )
    assert (
        materials.chunk("one", identity, original["chunk_id"])["locator"]
        == original["locator"]
    )
    assert materials.original("one", identity)["content"] == raw
    assert materials.get("one", identity)["readable_pages"] == 2
    assert materials.ocr_page("one", identity, 1)["state"] == "confirmed"
    assert (
        materials.ocr_page("one", identity, 1)["text"]
        == "第一章：先提出问题，然后核对证据。" * 100
    )
    assert coach.topic_part("one") == position and coach.active_topic("one") == topic
    assert coach.database_path.read_bytes() == before
    assert materials.retrieve("one", "第一章问题", material_id=identity)[0][
        "locator"
    ].startswith("PDF 第 1 页")


def test_out_of_order_ocr_pages_sort_by_real_page_and_do_not_overwrite_native_text(
    tmp_path,
):
    materials, identity, _ = book(tmp_path)
    assert save(materials, identity, 5, "第五页正文") == "saved"
    assert save(materials, identity, 1, "第一页正文") == "saved"
    assert [
        int(chunk["locator"].split()[2]) for chunk in materials.chunks("one", identity)
    ] == [1, 5, 12]
    before = materials.database_path.read_bytes()
    assert save(materials, identity, 12, "不能覆盖出版信息") == "existing"
    assert save(materials, identity, 1, "不能覆盖已保存文字") == "existing"
    assert materials.database_path.read_bytes() == before


def test_concurrent_duplicate_saves_are_atomic(tmp_path):
    materials, identity, _ = book(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: save(materials, identity), range(2)))
    assert sorted(results) == ["existing", "saved"]
    assert materials.get("one", identity)["readable_pages"] == 2
    assert len(materials.chunks("one", identity)) == 2


@pytest.mark.parametrize(
    "number,text,confidence,digest",
    [
        (0, "文字", 90, None),
        (13, "文字", 90, None),
        (1, "", 90, None),
        (1, "x" * 40001, 90, None),
        (1, "bad\x00text", 90, None),
        (1, "文字", 101, None),
        (1, "文字", True, None),
        (1, "文字", 90, "wrong"),
    ],
    ids=["zero", "outside", "empty", "long", "control", "confidence", "bool", "digest"],
)
def test_invalid_pages_are_rejected_without_partial_writes(
    tmp_path, number, text, confidence, digest
):
    materials, identity, _ = book(tmp_path)
    before = materials.database_path.read_bytes()
    with pytest.raises(MaterialError):
        save(materials, identity, number, text, confidence, digest=digest)
    assert materials.database_path.read_bytes() == before


def test_other_account_cannot_read_or_save_page(tmp_path):
    materials, identity, _ = book(tmp_path)
    assert materials.ocr_page("two", identity, 1) is None
    assert save(materials, identity, user="two") == "missing"
    assert materials.get("one", identity)["readable_pages"] == 1


def test_text_quota_is_atomic(tmp_path, monkeypatch):
    import coach.material_ocr as ocr

    materials, identity, _ = book(tmp_path)
    monkeypatch.setattr(
        ocr, "MAX_TEXT", materials.get("one", identity)["char_count"] + 2
    )
    with pytest.raises(MaterialError, match="200 万"):
        save(materials, identity, text="超出文字限额")
    assert materials.ocr_page("one", identity, 1)["state"] == "missing"


def test_old_library_schema_is_migrated_additively(tmp_path):
    materials, identity, raw = book(tmp_path)
    with sqlite3.connect(materials.database_path) as db:
        db.execute("DROP TABLE material_ocr_pages")
    restarted = MaterialRepository(materials.database_path)
    assert restarted.original("one", identity)["content"] == raw
    assert save(restarted, identity) == "saved"
    assert save(MaterialRepository(materials.database_path), identity) == "existing"


def test_pinned_official_assets_and_language_models_match_recorded_hashes():
    root = Path(__file__).parents[1] / "api/static/vendor/tesseract"
    provenance = json.loads((root / "PROVENANCE.json").read_text(encoding="utf-8"))
    for name, expected in provenance["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    for name in ("chi_sim.traineddata", "chi_tra.traineddata", "eng.traineddata"):
        raw = gzip.decompress((root / "lang" / (name + ".gz")).read_bytes())
        assert (
            hashlib.sha256(raw).hexdigest()
            == provenance["sources"]["tessdata_fast"][name]["sha256"]
        )
    assert "Apache License" in (root / "js/LICENSE.md").read_text(encoding="utf-8")
