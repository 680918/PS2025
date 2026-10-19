import hashlib
import sqlite3

import pytest

from coach import materials as module
from coach.materials import MaterialError, MaterialRepository, original_download_name
from tests.test_coach_materials import pdf_bytes


@pytest.mark.parametrize(
    "kind,raw",
    [
        ("txt", b"\xef\xbb\xbfLine one\r\nLine two\r\n"),
        ("txt", "中文原件\r\n保持原编码。".encode("utf-16")),
        ("txt", "中文原件\r\n保持原编码。".encode("gb18030")),
        ("md", b"# Heading\r\n\r\n    code()\n"),
        ("paste", "粘贴原文\r\n保留换行。".encode()),
    ],
)
def test_original_bytes_are_owned_unchanged_and_survive_rename_and_reopen(
    tmp_path, kind, raw
):
    repo = MaterialRepository(tmp_path / "library.db")
    identity = repo.add(
        "one",
        "original." + ("txt" if kind == "paste" else kind),
        raw,
        title="原名称",
        pasted=kind == "paste",
    )
    repo.add("two", "private.txt", b"Other user content", title="他人的原件")
    before = repo.database_path.read_bytes()
    assert repo.original("one", identity) == {
        "title": "原名称",
        "kind": kind,
        "content": raw,
    }
    assert repo.original("two", identity) is None
    assert repo.original("one", "missing") is None
    assert repo.database_path.read_bytes() == before
    assert repo.rename("one", identity, "新名称", expected_title="原名称")
    item = MaterialRepository(repo.database_path).original("one", identity)
    assert (
        item["title"] == "新名称"
        and hashlib.sha256(item["content"]).digest() == hashlib.sha256(raw).digest()
    )


def test_pdf_original_is_the_whole_uploaded_file_not_extracted_text(tmp_path):
    repo = MaterialRepository(tmp_path / "library.db")
    raw = pdf_bytes()
    identity = repo.add("one", "book.pdf", raw, title="自学书籍")
    before = repo.database_path.read_bytes()
    assert repo.original("one", identity)["content"] == raw
    assert repo.original("one", identity)["kind"] == "pdf"
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize("damage", ["digest", "empty", "text", "oversize"])
def test_corrupt_or_out_of_bound_original_is_not_returned(
    tmp_path, monkeypatch, damage
):
    repo = MaterialRepository(tmp_path / "library.db")
    identity = repo.add("one", "book.txt", b"Read the original text.")
    with sqlite3.connect(repo.database_path) as db:
        if damage == "digest":
            db.execute(
                "UPDATE materials SET digest=? WHERE material_id=?",
                ("0" * 64, identity),
            )
        elif damage == "empty":
            db.execute(
                "UPDATE materials SET raw=? WHERE material_id=?", (b"", identity)
            )
        elif damage == "text":
            db.execute(
                "UPDATE materials SET raw=? WHERE material_id=?",
                ("not a blob", identity),
            )
        else:
            monkeypatch.setattr(module, "MAX_FILE_BYTES", 8)
    before = repo.database_path.read_bytes()
    with pytest.raises(MaterialError):
        repo.original("one", identity)
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize(
    "title,kind,expected",
    [
        ("学习之道", "pdf", "学习之道.pdf"),
        ("学习之道.PDF", "pdf", "学习之道.pdf"),
        ("笔记", "paste", "笔记.txt"),
        ("CON", "txt", "资料-CON.txt"),
        ("con.txt", "txt", "资料-con.txt"),
        ("NUL.text", "md", "资料-NUL.text.md"),
        ("COM¹", "txt", "资料-COM¹.txt"),
        ("../../学习:计划?", "pdf", "_.._学习_计划_.pdf"),
        ("line\r\nX: header", "txt", "line__X_ header.txt"),
        ("fake\u202etxt", "pdf", "fake_txt.pdf"),
        (" ... ", "txt", "资料.txt"),
    ],
)
def test_attachment_names_are_safe_and_keep_canonical_extension(title, kind, expected):
    assert original_download_name(title, kind) == expected


def test_long_names_are_bounded_and_unsupported_types_are_not_downloaded():
    assert len(original_download_name("长" * 300, "pdf")) == 84
    with pytest.raises(MaterialError):
        original_download_name("程序", "exe")
