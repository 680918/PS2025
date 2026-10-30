import re
from html import unescape

import pytest
from fastapi.testclient import TestClient

from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from tests.test_web_book_reader import image_book
from tests.test_web_coach_dialogue import BASE, login, form, add_user
from tests.test_web_library import (
    setup as setup,
    password_hash as password_hash,
    no_real_services as no_real_services,
)


def seed(setup):
    _, client, user, _, directory = setup
    login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.add(user.user_id, "scan.pdf", image_book(), title="扫描页")
    path = f"/web/materials/{identity}/ocr"
    html = client.get(f"/web/materials/{identity}/read").text
    csrf = unescape(re.search(r'data-csrf="([^"]+)"', html)[1])
    info = client.get(path + "?page=1").json()
    values = dict(
        csrf=csrf,
        page="1",
        text="第一章：运用间隔复习。",
        confidence="92",
        digest=info["digest"],
    )
    return materials, identity, path, values


def test_reviewed_save_retrieval_and_guide_are_explicit_and_owned(setup):
    _, client, user, calls, directory = setup
    materials, identity, path, values = seed(setup)
    conversation_before = (directory / "coach_conversations.db").read_bytes()
    before = materials.database_path.read_bytes()
    assert client.get(path + "?page=1").json()["state"] == "missing"
    assert materials.database_path.read_bytes() == before and calls == []
    response = client.post(path, data=values, headers={"accept": "application/json"})
    assert response.status_code == 200 and response.json()["state"] == "confirmed"
    assert materials.get(user.user_id, identity)["readable_pages"] == 2
    assert calls == []
    preview = client.get(response.json()["preview_url"])
    assert "本页文字来自本地 OCR" in preview.text
    assert (directory / "coach_conversations.db").read_bytes() == conversation_before
    assert client.post(path, data=values).status_code == 409
    assert len(materials.chunks(user.user_id, identity)) == 2
    repo = CoachRepository(directory / "coach_conversations.db")
    repo.create_topic(user.user_id, "扫描书导学", identity)
    assert (
        client.post(
            "/web/coach/message",
            data={**form(client), "message": "第一章间隔复习怎么用"},
        ).status_code
        == 200
    )
    assert len(calls) == 1 and calls[0]["sources"][0]["excerpt"] == values["text"]
    assert calls[0]["sources"][0]["locator"].startswith("PDF 第 1 页")


def test_reader_page_can_prefill_unsaved_learning_unit_only_after_text_is_available(
    setup,
):
    _, client, user, calls, directory = setup
    materials, identity, path, values = seed(setup)
    databases = [materials.database_path, directory / "coach_conversations.db"]
    before = {database: database.read_bytes() for database in databases}
    missing = client.get(
        f"/web/materials/{identity}/read/unit?page=1", follow_redirects=False
    )
    assert (
        missing.status_code == 303
        and missing.headers["location"]
        == f"/web/materials/{identity}/read?page=1#book-ocr"
    )
    assert all(database.read_bytes() == data for database, data in before.items())
    assert client.post(path, data=values).status_code == 200
    after_save = {database: database.read_bytes() for database in databases}
    prepared = client.get(
        f"/web/materials/{identity}/read/unit?page=1", follow_redirects=False
    )
    assert (
        prepared.status_code == 303
        and prepared.headers["location"]
        == f"/web/materials/{identity}/plan/new?start=1&end=1"
    )
    editor = client.get(prepared.headers["location"])
    assert 'value="第 1 页"' in editor.text
    assert 'name="start_pos" type="number" min="1" required value="1"' in editor.text
    assert 'name="end_pos" type="number" min="1" required value="1"' in editor.text
    assert all(database.read_bytes() == data for database, data in after_save.items())
    assert calls == []


@pytest.mark.parametrize(
    "query",
    ["", "?page=0", "?page=13", "?page=x", "?page=1&page=1", "?page=1&x=1"],
)
def test_reader_unit_link_checks_one_owned_pdf_page_without_writes(setup, query):
    _, client, _, calls, _ = setup
    _, identity, _, _ = seed(setup)
    response = client.get(f"/web/materials/{identity}/read/unit" + query)
    assert response.status_code == 400 and calls == []


@pytest.mark.parametrize(
    "query",
    ["?start=0&end=1", "?start=1", "?start=1&end=1&end=1", "?start=1&end=1&x=1"],
)
def test_prefilled_unit_editor_checks_range_without_creating_unit(setup, query):
    _, client, user, calls, directory = setup
    materials, identity, path, values = seed(setup)
    assert client.post(path, data=values).status_code == 200
    before = (directory / "coach_conversations.db").read_bytes()
    response = client.get(f"/web/materials/{identity}/plan/new" + query)
    assert response.status_code == 400
    assert (directory / "coach_conversations.db").read_bytes() == before
    assert (
        calls == []
        and materials.ocr_page(user.user_id, identity, 1)["state"] == "confirmed"
    )


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("csrf", 403),
        ("page", 400),
        ("confidence", 400),
        ("empty", 400),
        ("digest", 400),
        ("origin", 403),
        ("extra", 403),
        ("duplicate", 403),
    ],
)
def test_bad_ocr_save_is_rejected_without_writes(setup, mutation, code):
    _, client, _, calls, _ = setup
    materials, identity, path, values = seed(setup)
    headers = {}
    if mutation == "csrf":
        values["csrf"] = "bad"
    if mutation == "page":
        values["page"] = "13"
    if mutation == "confidence":
        values["confidence"] = "999"
    if mutation == "empty":
        values["text"] = " "
    if mutation == "digest":
        values["digest"] = "wrong"
    if mutation == "origin":
        headers["origin"] = "https://other.example"
    if mutation == "extra":
        values["extra"] = "bad"
    if mutation == "duplicate":
        values = (
            "&".join(f"{key}={value}" for key, value in values.items() if key != "text")
            + "&text=x&text=y"
        )
        headers["content-type"] = "application/x-www-form-urlencoded"
    before = materials.database_path.read_bytes()
    assert client.post(path, data=values, headers=headers).status_code == code
    assert materials.database_path.read_bytes() == before and calls == []


@pytest.mark.parametrize(
    "query", ["", "?page=0", "?page=13", "?page=x", "?page=1&page=1", "?page=1&x=1"]
)
def test_status_parameters_are_checked(setup, query):
    _, client, _, calls, _ = setup
    _, _, path, _ = seed(setup)
    assert client.get(path + query).status_code == 400 and calls == []


def test_signed_out_or_other_user_cannot_read_or_write_ocr(setup, password_hash):
    app, client, _, calls, directory = setup
    materials, identity, path, values = seed(setup)
    add_user(directory, password_hash, "two@example.com", "其他人")
    with TestClient(app, base_url=BASE) as other:
        assert other.get(path + "?page=1", follow_redirects=False).status_code == 303
        login(other, "two@example.com")
        assert other.get(path + "?page=1").status_code == 404
        assert other.post(path, data=values).status_code == 403
    assert materials.ocr_page("none", identity, 1) is None and calls == []


def test_confirmed_ocr_survives_existing_whole_space_backup_and_restore(setup):
    from coach import local_backup as backup

    _, client, user, calls, directory = setup
    materials, identity, path, values = seed(setup)
    original = materials.original(user.user_id, identity)["content"]
    assert client.post(path, data=values).status_code == 200
    (directory / ".coach-mode").write_text("real", encoding="ascii")
    archive = backup.create_backup(
        directory, directory.parent / (directory.name + "-archive.zip")
    )
    target = directory.parent / (directory.name + "-restored")
    assert backup.restore_backup(archive, target)["mode"] == "real"
    restored = MaterialRepository(target / "coach_library.db")
    assert restored.ocr_page(user.user_id, identity, 1)["state"] == "confirmed"
    assert restored.ocr_page(user.user_id, identity, 1)["text"] == values["text"]
    assert restored.original(user.user_id, identity)["content"] == original
    assert calls == []
