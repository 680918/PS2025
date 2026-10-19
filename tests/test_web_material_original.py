import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from urllib.parse import unquote

import pytest

from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from tests import test_web_library as base
from tests.test_web_coach_dialogue import login
from tests.test_coach_materials import pdf_bytes

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def seed(
    user, directory, raw=b"Original bytes\r\n", filename="book.txt", title="学习原件"
):
    repo = MaterialRepository(directory / "coach_library.db")
    identity = repo.add(user.user_id, filename, raw, title=title)
    return repo, identity, "/web/materials/" + identity + "/original"


@pytest.mark.parametrize("kind", ["pdf", "txt", "md", "paste"])
def test_authenticated_attachment_is_exact_private_readonly_and_linked_from_existing_pages(
    setup, kind
):
    _, client, user, calls, directory = setup
    login(client)
    raw = pdf_bytes() if kind == "pdf" else "原始书籍\r\n保留完整原文。".encode()
    repo = MaterialRepository(directory / "coach_library.db")
    identity = repo.add(
        user.user_id,
        "file." + ("txt" if kind == "paste" else kind),
        raw,
        title="中文资料名称",
        pasted=kind == "paste",
    )
    path = "/web/materials/" + identity + "/original"
    dialogue = CoachRepository(directory / "coach_conversations.db", materials=repo)
    dialogue.create_topic(user.user_id, "原学习位置", identity)
    part = repo.chunks(user.user_id, identity)[0]
    dialogue.select_material_part(
        user.user_id, identity, "中文资料名称", part["chunk_id"]
    )
    before = {p: p.read_bytes() for p in (repo.database_path, dialogue.database_path)}
    for source in (
        "/web/materials",
        "/web/materials/" + identity,
        "/web/materials/" + identity + "/plan",
    ):
        page = client.get(source)
        assert (
            page.status_code == 200
            and 'href="' + path + '"' in page.text
            and "下载原件" in page.text
        )
    response = client.get(path)
    assert response.status_code == 200 and response.content == raw
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-length"] == str(len(raw))
    assert (
        response.headers["cache-control"] == "no-store"
        and response.headers["x-content-type-options"] == "nosniff"
    )
    assert response.headers["referrer-policy"] == "no-referrer"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert unquote(disposition.split("filename*=UTF-8''", 1)[1]) == "中文资料名称." + (
        "txt" if kind == "paste" else kind
    )
    assert (
        all(p.read_bytes() == content for p, content in before.items()) and calls == []
    )


def test_rename_changes_only_attachment_name_and_dangerous_title_stays_in_encoded_header(
    setup,
):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path = seed(user, directory)
    repo.rename(user.user_id, identity, "新的阅读名称.PDF", expected_title="学习原件")
    response = client.get(path)
    assert response.content == b"Original bytes\r\n"
    assert (
        unquote(
            response.headers["content-disposition"].split("filename*=UTF-8''", 1)[1]
        )
        == "新的阅读名称.PDF.txt"
    )
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "UPDATE materials SET title=? WHERE material_id=?",
            ("CON\r\nContent-Type: text/html", identity),
        )
    unsafe = client.get(path)
    assert (
        unsafe.status_code == 200
        and unsafe.headers["content-type"] == "application/octet-stream"
    )
    assert (
        "\r" not in unsafe.headers["content-disposition"]
        and "\n" not in unsafe.headers["content-disposition"]
    )
    assert calls == []


def test_guest_other_account_and_unknown_id_do_not_expose_original_and_release_capacity(
    setup,
):
    _, client, user, _, directory = setup
    repo, identity, path = seed(user, directory)
    assert client.get(path, follow_redirects=False).status_code == 303
    login(client)
    other = repo.add("other-user", "secret.txt", b"private content")
    assert client.get("/web/materials/" + other + "/original").status_code == 404
    assert client.get("/web/materials/" + "0" * 32 + "/original").status_code == 404
    assert client.get(path).content == b"Original bytes\r\n"


@pytest.mark.parametrize(
    "headers", [{"origin": "https://other.invalid"}, {"sec-fetch-site": "cross-site"}]
)
def test_foreign_origin_is_rejected(setup, headers):
    _, client, user, _, directory = setup
    login(client)
    _, _, path = seed(user, directory)
    assert client.get(path, headers=headers).status_code == 403


def test_extra_query_parameters_and_invalid_identity_are_rejected(setup):
    _, client, user, _, directory = setup
    login(client)
    _, _, path = seed(user, directory)
    assert (
        client.get(
            path, params={"user_id": "other", "filename": "override.html"}
        ).status_code
        == 400
    )
    assert client.get("/web/materials/not-an-id/original").status_code == 404


def test_unreadable_original_and_database_errors_are_safe_and_slots_are_released(
    setup, monkeypatch
):
    _, client, user, calls, directory = setup
    login(client)
    repo, _, path = seed(user, directory)
    original = MaterialRepository.original

    def broken(*a, **k):
        raise sqlite3.OperationalError("private database path and user content")

    monkeypatch.setattr(MaterialRepository, "original", broken)
    for _ in range(2):
        response = client.get(path)
        assert response.status_code == 503 and "private database" not in response.text
    monkeypatch.setattr(MaterialRepository, "original", original)
    assert client.get(path).status_code == 200
    with sqlite3.connect(repo.database_path) as db:
        db.execute("UPDATE materials SET digest=?", ("0" * 64,))
    response = client.get(path)
    assert (
        response.status_code == 503
        and "attachment" not in response.headers.get("content-disposition", "")
        and calls == []
    )


def test_original_download_is_rate_limited_without_ai_or_record_changes(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo, _, path = seed(user, directory)
    before = repo.database_path.read_bytes()
    for _ in range(6):
        assert client.get(path).status_code == 200
    limited = client.get(path)
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    assert repo.database_path.read_bytes() == before and calls == []


def test_parallel_download_preparation_is_bounded_and_capacity_recovers(
    setup, monkeypatch
):
    _, client, user, _, directory = setup
    login(client)
    _, _, path = seed(user, directory)
    original = MaterialRepository.original
    entered = Barrier(3)
    release = Event()

    def held(*a, **k):
        entered.wait(timeout=10)
        assert release.wait(timeout=10)
        return original(*a, **k)

    monkeypatch.setattr(MaterialRepository, "original", held)
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(client.get, path) for _ in range(2)]
        try:
            entered.wait(timeout=10)
            assert client.get(path).status_code == 503
        finally:
            release.set()
        assert all(
            request.result(timeout=10).status_code == 200 for request in requests
        )
    monkeypatch.setattr(MaterialRepository, "original", original)
    assert (
        hashlib.sha256(client.get(path).content).digest()
        == hashlib.sha256(b"Original bytes\r\n").digest()
    )
