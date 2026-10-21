"""Original reading stays available independently of OCR and of the JS reader."""

import re

import pytest
from fastapi.testclient import TestClient

from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from tests.test_web_book_reader import image_book
from tests.test_web_coach_dialogue import BASE, add_user, login
from tests.test_web_library import (
    setup as setup,
    no_real_services as no_real_services,
    password_hash as password_hash,
)


def seed(setup, kind="pdf"):
    _, client, user, _, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    raw = image_book(208) if kind == "pdf" else b"Private original text."
    identity = materials.add(user.user_id, "reading." + kind, raw, title="原文阅读")
    return materials, identity, raw, f"/web/materials/{identity}/read"


def test_scanned_book_prioritizes_full_reading_and_offers_independent_pdf_viewer(setup):
    _, client, user, calls, directory = setup
    materials, identity, raw, path = seed(setup)
    dialogue = CoachRepository(directory / "coach_conversations.db")
    before = {
        p: p.read_bytes() for p in (materials.database_path, dialogue.database_path)
    }
    response = client.get(path + "?page=10")
    assert response.status_code == 200
    html = response.text
    assert "直接阅读原始 PDF，共 208 页" in html
    assert "无需先识别文字" in html
    detail = re.search(
        r'<details class="reader-extraction"[^>]*>(.*?)</details>', html, re.S
    )
    assert detail and "open" not in detail[0].split(">", 1)[0]
    assert "1 / 208 页（不影响原书阅读）" in detail[1]
    assert html.index('class="reader-toolbar"') < detail.start()
    assert (
        f'href="{path}/pdf#page=10" target="_blank" rel="noopener noreferrer"' in html
    )
    assert 'aria-label="原书加载进度"' in html
    inline = client.get(path + "/pdf")
    assert inline.content == raw and inline.headers["content-type"] == "application/pdf"
    assert inline.headers["content-disposition"].startswith("inline;")
    assert inline.headers["content-length"] == str(len(raw))
    assert inline.headers["cache-control"] == "no-store"
    assert inline.headers["x-content-type-options"] == "nosniff"
    assert "object-src 'self'" in inline.headers["content-security-policy"]
    assert "default-src 'none'" in inline.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in inline.headers["content-security-policy"]
    attachment = client.get(f"/web/materials/{identity}/original")
    assert attachment.content == raw
    assert attachment.headers["content-disposition"].startswith("attachment;")
    assert all(p.read_bytes() == value for p, value in before.items()) and calls == []


@pytest.mark.parametrize("kind", ["txt", "md"])
def test_non_pdf_still_uses_text_reader_and_cannot_be_served_inline_as_pdf(setup, kind):
    _, client, _, calls, _ = setup
    _, _, raw, path = seed(setup, kind)
    response = client.get(path)
    assert response.status_code == 200 and "reader-direct" not in response.text
    assert client.get(path + "/pdf").status_code == 404
    assert client.get(path + "/pages").json()["pages"][0]["text"] == raw.decode()
    assert calls == []


def test_inline_pdf_checks_signin_and_owner(setup, password_hash):
    app, client, _, calls, directory = setup
    materials, identity, _, path = seed(setup)
    add_user(directory, password_hash, "two@example.com", "另一个读者")
    with TestClient(app, base_url=BASE) as other:
        assert other.get(path + "/pdf", follow_redirects=False).status_code == 303
        login(other, "two@example.com")
        assert other.get(path + "/pdf").status_code == 404
    assert client.get("/web/materials/" + "f" * 32 + "/read/pdf").status_code == 404
    assert calls == []


@pytest.mark.parametrize(
    "query,headers,code",
    [
        ("?page=1", {}, 400),
        ("?name=override.html", {}, 400),
        ("", {"origin": "https://other.example"}, 403),
        ("", {"sec-fetch-site": "cross-site"}, 403),
    ],
)
def test_inline_pdf_rejects_parameters_and_foreign_origins(setup, query, headers, code):
    _, client, _, calls, _ = setup
    materials, _, _, path = seed(setup)
    before = materials.database_path.read_bytes()
    assert client.get(path + "/pdf" + query, headers=headers).status_code == code
    assert materials.database_path.read_bytes() == before and calls == []


def test_direct_and_download_routes_share_existing_resource_limits(setup):
    _, client, _, calls, _ = setup
    _, identity, _, path = seed(setup)
    for _ in range(3):
        assert client.get(path + "/pdf").status_code == 200
        assert client.get(f"/web/materials/{identity}/original").status_code == 200
    limited = client.get(path + "/pdf")
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    assert calls == []
