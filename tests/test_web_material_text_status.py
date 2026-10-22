import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from coach.materials import MaterialRepository
from tests.test_web_book_reader import image_book
from tests.test_web_coach_dialogue import BASE, login, add_user
from tests.test_web_material_ocr import seed
from tests.test_web_library import (
    setup as setup,
    password_hash as password_hash,
    no_real_services as no_real_services,
)


def file_pages(html):
    return list(map(int, re.findall(r'data-file-page="(\d+)"', html)))


def test_read_only_overview_links_preparation_and_approval_refresh(setup):
    _, client, user, calls, directory = setup
    repo, identity, ocr, values = seed(setup)
    base = f"/web/materials/{identity}"
    paths = (repo.database_path, directory / "coach_conversations.db")
    before = {path: path.read_bytes() for path in paths}
    response = client.get(base + "/text-status")
    assert response.status_code == 200
    assert response.text.count("<h1>") == 1
    assert response.headers["cache-control"] == "no-store"
    assert "已提取文字 1 页 · OCR 已核对保存 0 页 · 尚无文字 11 页" in response.text
    assert f"{base}/read?page=1#book-ocr" in response.text
    assert file_pages(response.text) == list(range(1, 13))
    for path in ("/web/materials", base, base + "/read"):
        assert base + "/text-status" in client.get(path).text
    prepared = client.get(base + "/read?page=1")
    assert 'id="ocr-range-form"' in prepared.text
    assert (
        all(path.read_bytes() == data for path, data in before.items()) and calls == []
    )
    assert client.post(ocr, data=values).status_code == 200
    before = {path: path.read_bytes() for path in paths}
    response = client.get(base + "/text-status")
    assert "已提取文字 1 页 · OCR 已核对保存 1 页 · 尚无文字 10 页" in response.text
    assert f"{base}/read?page=2#book-ocr" in response.text
    assert values["text"] not in response.text and values["digest"] not in response.text
    assert file_pages(client.get(base + "/text-status?status=confirmed").text) == [1]
    assert file_pages(client.get(base + "/text-status?status=native").text) == [12]
    assert file_pages(client.get(base + "/text-status?status=missing").text) == list(
        range(2, 12)
    )
    assert (
        all(path.read_bytes() == data for path, data in before.items()) and calls == []
    )
    assert repo.reading_position(user.user_id, identity) == {"page": 1, "revision": 0}


def test_pagination_empty_filter_and_last_page_do_not_lose_state(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo = MaterialRepository(directory / "coach_library.db")
    identity = repo.add(
        user.user_id, "scan.pdf", image_book(54), title="<script>fictional</script>"
    )
    path = f"/web/materials/{identity}/text-status"
    before = repo.database_path.read_bytes()
    first = client.get(path + "?status=missing&p=1")
    assert file_pages(first.text) == list(range(1, 51))
    assert "status=missing&p=2" in first.text
    second = client.get(path + "?status=missing&p=2")
    assert file_pages(second.text) == [51, 52, 53]
    assert "status=missing&p=1" in second.text
    assert "<script>fictional</script>" not in second.text
    assert "&lt;script&gt;fictional&lt;/script&gt;" in second.text
    empty = client.get(path + "?status=confirmed")
    assert empty.status_code == 200 and file_pages(empty.text) == []
    assert "暂时没有文件页" in empty.text
    assert repo.database_path.read_bytes() == before and calls == []


@pytest.mark.parametrize(
    "query",
    [
        "?p=0",
        "?p=2",
        "?p=-1",
        "?p=01",
        "?p=1.5",
        "?p=9999",
        "?p=1&p=1",
        "?status=wrong",
        "?status=missing&status=native",
        "?extra=1",
        "?status=%3Cscript%3E",
    ],
)
def test_invalid_filters_do_not_mutate_or_call_services(setup, query):
    _, client, _, calls, directory = setup
    repo, identity, _, _ = seed(setup)
    before = {
        path: path.read_bytes()
        for path in (repo.database_path, directory / "coach_conversations.db")
    }
    assert (
        client.get(f"/web/materials/{identity}/text-status" + query).status_code == 400
    )
    assert (
        all(path.read_bytes() == value for path, value in before.items())
        and calls == []
    )


def test_signed_out_foreign_and_non_pdf_materials_are_not_disclosed(
    setup, password_hash
):
    app, client, user, calls, directory = setup
    repo, identity, _, _ = seed(setup)
    text = repo.add(user.user_id, "notes.txt", "不展示给别人。".encode())
    add_user(directory, password_hash, "two@example.com", "其他人")
    path = f"/web/materials/{identity}/text-status"
    with TestClient(app, base_url=BASE) as other:
        assert other.get(path, follow_redirects=False).status_code == 303
        login(other, "two@example.com")
        assert other.get(path).status_code == 404
    assert client.get(f"/web/materials/{text}/text-status").status_code == 404
    assert client.get("/web/materials/" + "0" * 32 + "/text-status").status_code == 404
    assert calls == []


def test_all_pages_available_offer_no_unnecessary_recognition(setup):
    _, client, _, calls, _ = setup
    _, identity, ocr, values = seed(setup)
    for number in range(1, 12):
        assert client.post(ocr, data={**values, "page": str(number)}).status_code == 200
    response = client.get(f"/web/materials/{identity}/text-status")
    assert "每页都已有可引用文字" in response.text
    assert (
        "准备下一批识别" not in response.text
        and "准备本页起的识别" not in response.text
    )
    assert calls == []


def test_database_failure_gives_retry_message_without_internal_details(
    setup, monkeypatch
):
    _, client, _, calls, _ = setup
    _, identity, _, _ = seed(setup)

    def unavailable(*args):
        raise sqlite3.OperationalError("private-database-marker")

    monkeypatch.setattr(MaterialRepository, "text_coverage", unavailable)
    response = client.get(f"/web/materials/{identity}/text-status")
    assert response.status_code == 503 and "稍后重试" in response.text
    assert "private-database-marker" not in response.text and calls == []
