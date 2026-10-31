"""Real PDF parsing and account journeys, with no real model or email calls."""

import io
import json
import re
from html import unescape

import pytest

from coach import materials as storage
from coach.dialogue import make_llm_responder
from coach.material_limits import (
    MAX_FILE_BYTES,
    MAX_LIBRARY_BYTES,
    MAX_PDF_PAGES,
    MAX_TEXT,
)
from coach.materials import MaterialError, MaterialRepository, parse_material
from conversation.coach_repository import CoachRepository
from tests.test_coach_materials import pdf_bytes
from tests.test_web_coach_dialogue import Forms, form, login
from tests.test_web_library import (
    no_real_services as no_real_services,
    password_hash as password_hash,
    setup as setup,
    upload,
)


def large_pdf():
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf_bytes())))
    writer.add_attachment("book-illustration.bin", b"x" * (11 * 1024**2))
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def book(client, title="影响力", author=""):
    values = Forms(client.get("/web/studies").text).values("/web/studies/book")
    return client.post(
        "/web/studies/book", data={**values, "title": title, "author": author}
    )


def test_full_large_book_upload_extract_download_and_export(setup):
    from api.asset_export import build_export
    from zipfile import ZipFile

    _, client, user, calls, directory = setup
    login(client)
    raw = large_pdf()
    assert 10 * 1024**2 < len(raw) < MAX_FILE_BYTES
    response = upload(client, filename="large-book.pdf", raw=raw)
    assert response.status_code == 200 and "Spaced practice" in response.text
    materials = MaterialRepository(directory / "coach_library.db")
    item = materials.list(user.user_id)[0]
    assert item["raw_bytes"] == len(raw) and item["readable_pages"] == 1
    assert client.get(f"/web/materials/{item['material_id']}/original").content == raw
    assert materials.original(user.user_id, item["material_id"])["content"] == raw
    assert materials.get("another-user", item["material_id"]) is None
    assert upload(client, filename="large-book.pdf", raw=raw).status_code == 200
    assert len(materials.list(user.user_id)) == 1
    archive = build_export(
        directory / "coach_conversations.db",
        directory / "coach_library.db",
        user.user_id,
        ["materials"],
    )
    with ZipFile(io.BytesIO(b"".join(archive.chunks()))) as zipped:
        originals = [name for name in zipped.namelist() if name.endswith(".pdf")]
        assert len(originals) == 1 and zipped.read(originals[0]) == raw
    assert calls == []


@pytest.mark.parametrize("pages,valid", [(501, True), (1501, False)])
def test_pdf_page_limit_is_shared_with_worker(pages, valid):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf_bytes())))
    for _ in range(pages - 1):
        writer.add_blank_page(width=300, height=200)
    output = io.BytesIO()
    writer.write(output)
    if valid:
        _, _, extracted, count = parse_material("book.pdf", output.getvalue())
        assert count == pages and extracted[0]["page"] == 1
    else:
        with pytest.raises(MaterialError, match="1500"):
            parse_material("book.pdf", output.getvalue())


def test_shared_limits_and_long_book_text(tmp_path):
    assert MAX_FILE_BYTES == 100 * 1024**2
    assert MAX_LIBRARY_BYTES == 300 * 1024**2
    assert MAX_PDF_PAGES == 1500 and MAX_TEXT == 2000000
    repo = MaterialRepository(tmp_path / "library.db")
    identity = repo.add("one", "long.txt", ("学习" * 300001).encode())
    assert repo.get("one", identity)["char_count"] == 600002
    with pytest.raises(MaterialError, match="200 万"):
        repo.add("one", "too-long.txt", b"x" * (MAX_TEXT + 1))
    with pytest.raises(MaterialError, match="5 万"):
        repo.add("one", "paste.txt", b"x" * 50001, pasted=True)
    assert len(repo.list("one")) == 1


def test_quota_rejection_is_atomic_and_duplicate_does_not_spend_storage(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(storage, "MAX_LIBRARY_BYTES", 15)
    repo = MaterialRepository(tmp_path / "library.db")
    identity = repo.add("one", "a.txt", b"abcdefghij")
    assert repo.add("one", "again.txt", b"abcdefghij") == identity
    with pytest.raises(MaterialError, match="300 MB"):
        repo.add("one", "b.txt", b"0123456789")
    assert (
        len(repo.list("one")) == 1
        and repo.original("one", identity)["content"] == b"abcdefghij"
    )
    assert repo.add("two", "b.txt", b"0123456789")


def test_upload_oversize_error_is_specific_and_does_not_write(setup, monkeypatch):
    import api.library_pages as pages

    _, client, user, calls, directory = setup
    login(client)
    monkeypatch.setattr(pages, "MAX_FILE_BYTES", 32)
    response = upload(client, raw=b"x" * 20000)
    assert response.status_code == 413 and "100 MB" in response.text
    assert "上传格式无法读取，或" not in response.text
    assert MaterialRepository(directory / "coach_library.db").list(user.user_id) == []
    assert calls == []


def test_catalog_keeps_upload_entry_and_moves_title_guidance_to_study_page(setup):
    _, client, _, calls, _ = setup
    login(client)
    response = client.get("/web/materials")
    assert 'href="/web/studies#book-reading"' not in response.text
    assert 'href="/web/materials/add#material-upload"' in response.text
    assert "300.00 MB" in response.text
    assert 'id="material-upload"' not in response.text
    add_page = client.get("/web/materials/add")
    assert "100 MB" in add_page.text and "1500 页" in add_page.text
    assert "200 万字" in add_page.text
    assert 'data-max-bytes="104857600"' in add_page.text
    assert 'src="/static/material-upload.js"' in add_page.text
    assert "script-src 'self'" in add_page.headers["content-security-policy"]
    assert Forms(add_page.text).values("/web/materials/upload?from=conversation")[
        "csrf"
    ]
    assert calls == []


def test_by_title_journey_preserves_other_book_and_waits_for_explicit_send(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    repo = CoachRepository(directory / "coach_conversations.db")
    previous_book = materials.add(user.user_id, "previous.txt", "原书内容".encode())
    materials.select(user.user_id, previous_book)
    repo.create_topic(user.user_id, "原来的学习", previous_book)
    previous = repo.active_topic(user.user_id)
    response = book(client, author="罗伯特·西奥迪尼")
    assert response.status_code == 200 and "按书名导读 · 未上传原书" in response.text
    active = repo.active_topic(user.user_id)
    assert active["title"] == "阅读《影响力》 · 罗伯特·西奥迪尼"
    assert active["material_id"] == "" and calls == []
    message = unescape(
        re.search(r'id="coach-message"[^>]*>(.*?)</textarea>', response.text, re.S)[1]
    )
    assert "核心观点" in message and "应用" in message and "《影响力》" in message
    assert repo.topic(user.user_id, previous["topic_id"]) == previous
    sent = client.post("/web/coach/message", data={**form(client), "message": message})
    assert sent.status_code == 200 and len(calls) == 1
    assert calls[0]["sources"] == [] and calls[0]["material"] is None
    assert repo.active_topic(user.user_id)["title"] == active["title"]
    # Ordinary reload never inserts or sends the starter again.
    normal = client.get("/web/welcome")
    assert re.search(r'id="coach-message"[^>]*></textarea>', normal.text)
    # Browser sends by fetch and reloads the same URL, keeping book_intro=1.
    refreshed = client.get("/web/welcome?book_intro=1")
    assert re.search(r'id="coach-message"[^>]*></textarea>', refreshed.text)
    assert book(client, author="罗伯特·西奥迪尼").status_code == 200
    assert len(repo.list_topics(user.user_id)) == 2 and len(calls) == 1
    assert repo.topic(user.user_id, previous["topic_id"]) == previous


def test_existing_title_keeps_user_uploaded_book_binding(setup):
    _, client, user, calls, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "book.txt", "已上传内容".encode())
    repo = CoachRepository(directory / "coach_conversations.db")
    repo.create_topic(user.user_id, "阅读《影响力》", identity)
    topic = repo.active_topic(user.user_id)
    assert book(client).status_code == 200
    assert repo.active_topic(user.user_id) == topic
    assert "按书名导读 · 未上传原书" not in client.get("/web/welcome?book_intro=1").text
    assert calls == []


@pytest.mark.parametrize(
    "title,author",
    [("", ""), ("x" * 81, ""), ("书", "x" * 25), ("书\n名", ""), ("书", "作\n者")],
    ids=["empty", "long-title", "long-author", "title-control", "author-control"],
)
def test_invalid_book_identity_creates_no_topic(setup, title, author):
    _, client, user, calls, directory = setup
    login(client)
    assert book(client, title, author).status_code == 400
    assert (
        CoachRepository(directory / "coach_conversations.db").list_topics(user.user_id)
        == []
    )
    assert calls == []


def test_book_form_checks_auth_origin_csrf_and_escapes_title(setup):
    _, client, user, calls, directory = setup
    assert (
        client.post("/web/studies/book", data={}, follow_redirects=False).status_code
        == 303
    )
    login(client)
    assert (
        client.post(
            "/web/studies/book", data={"title": "书", "author": "", "csrf": "bad"}
        ).status_code
        == 403
    )
    values = Forms(client.get("/web/studies").text).values("/web/studies/book")
    assert (
        client.post(
            "/web/studies/book",
            data=values,
            headers={"origin": "https://other.example"},
        ).status_code
        == 403
    )
    result = book(client, "<script>标题</script>")
    assert "&lt;script&gt;标题&lt;/script&gt;" in result.text
    assert "<script>标题</script>" not in result.text
    assert (
        calls == []
        and len(
            CoachRepository(directory / "coach_conversations.db").list_topics(
                user.user_id
            )
        )
        == 1
    )


def test_llm_has_explicit_title_based_guide_contract_without_fake_sources():
    captured = []

    def provider(system, payload):
        captured.append((system, json.loads(payload)))
        return {
            "status": "success",
            "content": json.dumps(
                {"reply": "通用导读，尚未核对原书。", "used_source_ids": []}
            ),
        }

    answer = make_llm_responder(provider)([], "我在读《影响力》，如何实际应用？", None)
    system, payload = captured[0]
    assert "不要因没有上传就拒绝正常导读" in system
    assert "先简短澄清" in system and "区分作者观点" in system
    assert "不确定" in system and "不要伪造引文、页码" in system
    assert payload["available_sources"] == [] and payload["selected_material"] is None
    assert answer.used_source_ids == []
