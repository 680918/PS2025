import io
from concurrent.futures import ThreadPoolExecutor

import pytest

from coach.materials import MaterialError, MaterialRepository, parse_material


def pdf_bytes(*, blank=False, encrypted=False):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    if not blank:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font)}
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(
            b"BT /F1 12 Tf 20 100 Td (Spaced practice improves learning.) Tj ET"
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("test-password")
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def test_pdf_worker_reads_real_text_and_actual_page_number():
    _, kind, pages, count = parse_material("test.pdf", pdf_bytes())
    assert kind == "pdf" and count == 1
    assert pages[0]["page"] == 1 and "Spaced practice" in pages[0]["text"]


@pytest.mark.parametrize(
    "raw, text",
    [
        (pdf_bytes(blank=True), "扫描版"),
        (pdf_bytes(encrypted=True), "加密"),
        (b"not PDF", "不是"),
        (b"%PDF-invalid", "无法解析"),
    ],
    ids=["scan", "encrypted", "wrong-header", "broken-pdf"],
)
def test_invalid_or_unsupported_pdf_is_rejected(raw, text):
    with pytest.raises(MaterialError, match=text):
        parse_material("test.pdf", raw)


@pytest.mark.parametrize(
    "raw",
    [
        "间隔练习帮助记忆。".encode("utf-8-sig"),
        "间隔练习帮助记忆。".encode("utf-16"),
        "间隔练习帮助记忆。".encode("gb18030"),
    ],
    ids=["utf8", "utf16", "gb18030"],
)
def test_common_chinese_text_encodings(raw):
    assert "间隔练习" in parse_material("book.txt", raw)[2][0]["text"]


@pytest.mark.parametrize(
    "name, raw",
    [
        ("x.exe", b"text"),
        ("x.txt", b""),
        ("x.md", b"\x00bad"),
        ("x.txt", b"a" * (10 * 1024**2 + 1)),
    ],
    ids=["unsupported", "empty", "binary", "oversize"],
)
def test_invalid_materials_are_rejected(name, raw):
    with pytest.raises(MaterialError):
        parse_material(name, raw)


def test_materials_are_private_persistent_and_retrieval_is_grounded(tmp_path):
    path = tmp_path / "library.db"
    repo = MaterialRepository(path)
    identity = repo.add(
        "one",
        "../../notes.md",
        ("# 学习\n间隔练习比集中重复更适合长期复习。\n" * 60).encode(),
    )
    assert repo.get("one", identity)["filename"] == "notes.md"
    assert repo.get("two", identity) is None and repo.chunks("two", identity) == []
    with pytest.raises(MaterialError):
        repo.select("two", identity)
    repo.select("one", identity)
    restarted = MaterialRepository(path)
    assert restarted.selected("one")["material_id"] == identity
    sources = restarted.retrieve("one", "间隔练习怎样使用？")
    assert 1 <= len(sources) <= 6 and all(
        "间隔练习" in source["excerpt"] for source in sources
    )
    assert all(source["locator"].startswith("片段 ") for source in sources)
    assert restarted.retrieve("two", "学习") == []
    assert restarted.retrieve("one", "周末天气预报") == []
    restarted.select("one", None)
    assert restarted.selected("one") is None


def test_duplicate_uploads_cannot_overwrite_and_concurrent_uploads_are_idempotent(
    tmp_path,
):
    repo = MaterialRepository(tmp_path / "library.db")
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(
                lambda title: repo.add(
                    "one", "book.txt", b"same learning text", title=title
                ),
                ["First", "Second"],
            )
        )
    assert ids[0] == ids[1] and len(repo.list("one")) == 1
    other = repo.add("two", "book.txt", b"same learning text")
    assert other != ids[0]


def test_trial_quota_and_paste_limits(tmp_path):
    repo = MaterialRepository(tmp_path / "library.db")
    for index in range(20):
        repo.add("one", f"{index}.txt", f"Learning note {index}".encode())
    with pytest.raises(MaterialError, match="20"):
        repo.add("one", "next.txt", b"another note")
    with pytest.raises(MaterialError, match="5 万"):
        repo.add("two", "paste.txt", ("字" * 50001).encode(), pasted=True)


def test_pdf_timeout_is_reported_without_writing_a_material(tmp_path, monkeypatch):
    import subprocess

    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("worker", 20)

    monkeypatch.setattr(subprocess, "run", timed_out)
    repo = MaterialRepository(tmp_path / "library.db")
    with pytest.raises(MaterialError, match="未能在本机完成"):
        repo.add("one", "book.pdf", b"%PDF-fake")
    assert repo.list("one") == []
