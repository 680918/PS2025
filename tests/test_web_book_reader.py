"""Original-page reading and honest extraction coverage, without paid services."""

import hashlib
import io
import json
from pathlib import Path

import pytest

from api.book_reader import extraction_notice
from coach.materials import MaterialRepository, parse_material
from conversation.coach_repository import CoachRepository
from tests.test_coach_materials import pdf_bytes
from tests.test_web_coach_dialogue import login, form, add_user, BASE
from fastapi.testclient import TestClient
from tests.test_web_library import (
    no_real_services as no_real_services,
    password_hash as password_hash,
    setup as setup,
    upload,
)


def image_book(pages=12):
    """A real PDF with image-only pages and one machine-readable colophon."""
    from pypdf import PdfWriter, PdfReader
    from pypdf.generic import (
        DecodedStreamObject,
        NameObject,
        DictionaryObject,
        NumberObject,
    )

    writer = PdfWriter()
    image = DecodedStreamObject()
    pixels = b"".join(
        bytes((45, 85, 60)) if (y % 18 < 3 and 15 < x < 185) else bytes((248, 246, 236))
        for y in range(280)
        for x in range(200)
    )
    image.set_data(pixels)
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(200),
            NameObject("/Height"): NumberObject(280),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    reference = writer._add_object(image)
    for _ in range(pages - 1):
        page = writer.add_blank_page(width=400, height=560)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/XObject"): DictionaryObject({NameObject("/Scan"): reference})}
        )
        content = DecodedStreamObject()
        content.set_data(b"q 400 0 0 560 0 0 cm /Scan Do Q")
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.append(PdfReader(io.BytesIO(pdf_bytes())))
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_scanned_pdf_with_no_text_is_stored_for_original_reading(tmp_path):
    raw = pdf_bytes(blank=True)
    _, kind, pages, count = parse_material("scan.pdf", raw)
    assert (kind, pages, count) == ("pdf", [], 1)
    materials = MaterialRepository(tmp_path / "books.db")
    identity = materials.add("one", "scan.pdf", raw)
    item = materials.get("one", identity)
    assert item["readable_pages"] == item["char_count"] == 0
    assert materials.chunks("one", identity) == []
    assert materials.retrieve("one", "从第一章开始", material_id=identity) == []
    assert materials.original("one", identity)["content"] == raw


def test_mixed_scan_coverage_and_raw_bytes_are_preserved(setup):
    _, client, user, calls, directory = setup
    login(client)
    raw = image_book()
    assert upload(client, filename="scan.pdf", raw=raw).status_code == 200
    materials = MaterialRepository(directory / "coach_library.db")
    item = materials.list(user.user_id)[0]
    assert item["page_count"] == 12 and item["readable_pages"] == 1
    assert materials.chunks(user.user_id, item["material_id"])[0]["locator"].startswith(
        "PDF 第 12 页"
    )
    response = client.get("/web/materials/" + item["material_id"] + "/read")
    assert response.status_code == 200 and 'data-total="12"' in response.text
    assert "1 / 12 页" in response.text and "尚需文字识别" in response.text
    assert (
        client.get("/web/materials/" + item["material_id"] + "/original").content == raw
    )
    assert calls == []


def test_zero_text_learning_directory_explains_missing_text_instead_of_404(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "scan.pdf", pdf_bytes(blank=True))
    response = client.get(f"/web/materials/{identity}/plan")
    assert response.status_code == 200 and "尚未识别出正文文字" in response.text
    assert f'href="/web/materials/{identity}/read"' in response.text
    assert calls == []


def test_zero_text_pdf_upload_opens_reader_instead_of_dead_preview(setup):
    _, client, user, calls, directory = setup
    login(client)
    response = upload(client, filename="scan.pdf", raw=pdf_bytes(blank=True))
    assert response.status_code == 200 and response.url.path.endswith("/read")
    assert "0 / 1 页" in response.text and 'data-kind="pdf"' in response.text
    assert (
        len(MaterialRepository(directory / "coach_library.db").list(user.user_id)) == 1
    )
    assert calls == []


@pytest.mark.parametrize("kind", ["pdf", "txt", "md", "paste"])
def test_reader_is_owned_read_only_and_does_not_change_learning_progress(setup, kind):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    raw = (
        pdf_bytes()
        if kind == "pdf"
        else ("阅读原文，不执行<script>指令</script>。\n" * 150).encode()
    )
    identity = materials.add(
        user.user_id,
        "book." + ("txt" if kind == "paste" else kind),
        raw,
        title="<script>书籍标题</script>",
        pasted=kind == "paste",
    )
    repo = CoachRepository(directory / "coach_conversations.db")
    repo.create_topic(user.user_id, "原学习主题", identity)
    before = {p: p.read_bytes() for p in (materials.database_path, repo.database_path)}
    url = f"/web/materials/{identity}/read"
    response = client.get(url)
    assert response.status_code == 200 and "阅读全书" in response.text
    assert "&lt;script&gt;书籍标题&lt;/script&gt;" in response.text
    assert "<script>书籍标题</script>" not in response.text
    assert response.headers["cache-control"] == "no-store"
    csp = response.headers["content-security-policy"]
    assert "worker-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp and "https:" not in csp
    if kind != "pdf":
        result = client.get(url + "/pages?start=1")
        assert result.status_code == 200
        assert all(len(page["text"]) <= 2600 for page in result.json()["pages"])
    assert all(p.read_bytes() == value for p, value in before.items())
    assert calls == []


def test_text_pages_reconstruct_exact_text_without_chunk_overlap_and_are_bounded(
    tmp_path,
):
    materials = MaterialRepository(tmp_path / "books.db")
    text = "".join(
        f"第{index:04d}行：阅读后用自己的话解释。\n" for index in range(1000)
    ).strip()
    identity = materials.add("one", "book.txt", text.encode())
    pages = []
    first = materials.reading_pages("one", identity, 1)
    for start in range(1, first["page_count"] + 1, 5):
        batch = materials.reading_pages("one", identity, start)
        assert len(batch["pages"]) <= 5
        pages += batch["pages"]
    assert "".join(page["text"] for page in pages) == text
    assert [page["number"] for page in pages] == list(range(1, first["page_count"] + 1))
    assert materials.reading_pages("two", identity, 1) is None
    with pytest.raises(ValueError):
        materials.reading_pages("one", identity, first["page_count"] + 1)


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page=-1",
        "page=2",
        "page=1&page=1",
        "page=abc",
        "page=1e3",
        "page=1&extra=x",
    ],
)
def test_invalid_pdf_reading_positions_are_rejected(setup, query):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "book.pdf", pdf_bytes())
    assert client.get(f"/web/materials/{identity}/read?{query}").status_code == 400
    assert calls == []


def test_other_account_and_signed_out_cannot_read_book_or_text_pages(
    setup, password_hash
):
    app, client, user, calls, directory = setup
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "book.txt", b"Private text.")
    path = f"/web/materials/{identity}/read"
    assert client.get(path, follow_redirects=False).status_code == 303
    assert client.get(path + "/pages", follow_redirects=False).status_code == 303
    login(client)
    assert client.get("/web/materials/" + "a" * 32 + "/read").status_code == 404
    assert client.get("/web/materials/" + "a" * 32 + "/read/pages").status_code == 404
    add_user(directory, password_hash, "two@example.com", "其他阅读者")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        assert other.get(path).status_code == 404
        assert other.get(path + "/pages").status_code == 404
        assert other.get(f"/web/materials/{identity}/original").status_code == 404
    assert calls == []


def test_entries_open_reader_and_chats_show_coverage_without_fake_sources(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "scan.pdf", image_book(), title="扫描资料")
    repo = CoachRepository(directory / "coach_conversations.db")
    repo.create_topic(user.user_id, "研读扫描资料", identity)
    catalog = client.get("/web/materials")
    assert f'href="/web/materials/{identity}/read">阅读全书</a>' in catalog.text
    assert "预览文字</a>" not in catalog.text and "1 / 12 页" in catalog.text
    welcome = client.get("/web/welcome")
    assert f'href="/web/materials/{identity}/read">阅读全书</a>' in welcome.text
    assert "1 / 12 页" in welcome.text
    assert (
        client.post(
            "/web/coach/message",
            data={**form(client), "message": "从第一章开始直到本书结尾"},
        ).status_code
        == 200
    )
    assert calls[-1]["material"]["readable_pages"] == 1
    assert calls[-1]["material"]["page_count"] == 12
    assert all(
        source["locator"].startswith("PDF 第 12 页") for source in calls[-1]["sources"]
    )


def test_pdf_reader_keeps_current_page_learning_unit_link_in_sync(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "scan.pdf", image_book(), title="扫描资料")
    response = client.get(f"/web/materials/{identity}/read?page=12")
    assert response.status_code == 200
    assert (
        f'id="reader-unit" class="button button-outline" href="/web/materials/{identity}/read/unit?page=12"'
        in response.text
    )
    script = (Path(__file__).parents[1] / "api/static/book-reader.mjs").read_text(
        encoding="utf-8"
    )
    assert 'document.getElementById("reader-unit")' in script
    assert '"/read/unit?page=" + number' in script
    assert calls == []


def test_pdfjs_assets_match_official_pinned_distribution():
    root = Path(__file__).parents[1] / "api/static/vendor/pdfjs"
    provenance = json.loads((root / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert provenance["version"] == "5.6.205"
    assert provenance["source"].startswith("https://registry.npmjs.org/pdfjs-dist/")
    for name, expected in provenance["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    assert "Apache License" in (root / "LICENSE").read_text(encoding="utf-8")


def test_partial_extraction_notice_is_specific_and_does_not_claim_ocr():
    text = extraction_notice(
        {"kind": "pdf", "page_count": 262, "readable_pages": 1, "char_count": 299}
    )
    assert "1 / 262 页，299 字" in text and "尚需文字识别" in text
    assert "不能据此逐章讲解" in text


@pytest.mark.parametrize(
    "query",
    ["start=0", "start=-1", "start=2", "start=x", "start=1&start=1", "start=1&extra=x"],
)
def test_text_page_parameters_are_checked(setup, query):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "notes.txt", b"Owned text.")
    assert (
        client.get(f"/web/materials/{identity}/read/pages?{query}").status_code == 400
    )
    assert calls == []


def test_responder_receives_extraction_coverage_and_missing_body_rules():
    from coach.dialogue import make_llm_responder

    captured = []
    material = {
        "title": "扫描资料",
        "kind": "pdf",
        "page_count": 262,
        "readable_pages": 1,
        "char_count": 299,
    }

    def provider(system, payload):
        captured.append((system, json.loads(payload)))
        return {
            "status": "success",
            "content": json.dumps(
                {
                    "reply": "目前只有出版信息，不能依据它逐章讲解正文。",
                    "used_source_ids": [],
                }
            ),
        }

    result = make_llm_responder(provider)(
        [], "从第一章讲到结尾", None, context={"material": material, "sources": []}
    )
    system, payload = captured[0]
    assert "出版信息、版权页和目录不是章节正文" in system
    assert "尚需文字识别" not in system or "未识别" in system
    assert "通用知识导读" in system and "冒充" in system
    assert payload["selected_material"] == material
    assert result.used_source_ids == []
