import pytest
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from tests.test_web_book_reader import image_book
from tests.test_web_coach_dialogue import BASE, Forms, add_user, form, login
from tests.test_web_library import (
    setup as setup,
    password_hash as password_hash,
    no_real_services as no_real_services,
)


def seed(setup, kind="pdf"):
    _, client, user, _, directory = setup
    if not client.cookies.get("coach_login_session"):
        login(client)
    materials = MaterialRepository(directory / "coach_library.db")
    raw = image_book(6) if kind == "pdf" else ("知识点阅读与练习。" * 1300).encode()
    identity = materials.add(user.user_id, "book." + kind, raw)
    path = f"/web/materials/{identity}/read"
    fields = Forms(client.get(path + "?page=2").text).values(path + "/position")
    return materials, identity, path, fields


@pytest.mark.parametrize("kind", ["pdf", "txt"])
def test_save_resume_explicit_jump_restart_and_learning_are_separate(setup, kind):
    _, client, user, calls, directory = setup
    materials, identity, path, fields = seed(setup, kind)
    repo = CoachRepository(directory / "coach_conversations.db")
    repo.create_topic(user.user_id, "书籍讨论", identity)
    conversation_before = repo.database_path.read_bytes()
    response = client.post(path + "/position", data=fields)
    assert response.status_code == 200 and 'data-initial="2"' in response.text
    before = materials.database_path.read_bytes()
    assert 'data-initial="2"' in client.get(path).text
    assert 'data-initial="1"' in client.get(path + "?page=1").text
    assert "继续阅读 · 第2页" in client.get("/web/materials").text
    assert materials.database_path.read_bytes() == before
    assert repo.database_path.read_bytes() == conversation_before and calls == []
    with TestClient(create_account_app(directory), base_url=BASE) as restarted:
        login(restarted)
        assert 'data-initial="2"' in restarted.get(path).text


def test_stale_form_returns_latest_position_without_overwriting(setup):
    _, client, user, calls, _ = setup
    materials, identity, path, fields = seed(setup, "txt")
    current = client.post(
        path + "/position", data=fields, headers={"accept": "application/json"}
    )
    assert current.json() == {"status": "saved", "page": 2, "revision": 1}
    response = client.post(
        path + "/position",
        data={**fields, "page": "3"},
        headers={"accept": "application/json"},
    )
    assert response.status_code == 409 and response.json()["page"] == 2
    assert materials.reading_position(user.user_id, identity)["page"] == 2
    assert calls == []


@pytest.mark.parametrize(
    "bad", ["csrf", "page", "revision", "extra", "origin", "duplicate", "oversize"]
)
def test_invalid_writes_are_rejected_without_data_changes(setup, bad):
    _, client, _, calls, _ = setup
    materials, _, path, fields = seed(setup, "txt")
    headers = {"accept": "application/json"}
    code = 403
    if bad == "csrf":
        fields["csrf"] = "wrong"
    if bad == "page":
        fields["page"] = "0"
        code = 400
    if bad == "revision":
        fields["revision"] = "-1"
        code = 400
    if bad == "extra":
        fields["user_id"] = "someone"
    if bad == "origin":
        headers["origin"] = "https://other.example"
    if bad == "duplicate":
        from urllib.parse import urlencode

        fields = urlencode(fields) + "&page=3"
        headers["content-type"] = "application/x-www-form-urlencoded"
    if bad == "oversize":
        fields["csrf"] = "x" * 3000
    before = materials.database_path.read_bytes()
    response = (
        client.post(path + "/position", content=fields, headers=headers)
        if isinstance(fields, str)
        else client.post(path + "/position", data=fields, headers=headers)
    )
    assert response.status_code == code
    assert materials.database_path.read_bytes() == before and calls == []


def test_signed_out_and_other_account_cannot_read_or_update_position(
    setup, password_hash
):
    app, client, _, calls, directory = setup
    materials, identity, path, fields = seed(setup, "txt")
    add_user(directory, password_hash, "two@example.com", "另一位用户")
    with TestClient(app, base_url=BASE) as other:
        assert (
            other.post(
                path + "/position", data=fields, follow_redirects=False
            ).status_code
            == 303
        )
        login(other, "two@example.com")
        assert other.get(path).status_code == 404
        assert other.get(path + "/learn?page=2").status_code == 404
        before = materials.database_path.read_bytes()
        assert other.post(path + "/position", data=fields).status_code == 403
        assert materials.database_path.read_bytes() == before
    assert calls == []


def test_current_page_routes_missing_scan_to_review_and_confirmed_text_to_chat(setup):
    _, client, user, calls, directory = setup
    materials, identity, path, _ = seed(setup)
    before = (directory / "coach_conversations.db").read_bytes()
    response = client.get(path + "/learn?page=2", follow_redirects=False)
    assert response.headers["location"] == path + "?page=2#book-ocr"
    assert (directory / "coach_conversations.db").read_bytes() == before
    info = materials.ocr_page(user.user_id, identity, 2)
    materials.save_ocr_page(
        user.user_id,
        identity,
        2,
        "本页核对的知识点，先回想再核对。",
        90,
        info["digest"],
    )
    preview = client.get(path + "/learn?page=2")
    assert "本页核对的知识点" in preview.text and "本页文字来自本地 OCR" in preview.text
    values = Forms(preview.text).values(f"/web/materials/{identity}/study")
    assert (
        client.post(f"/web/materials/{identity}/study", data=values).status_code == 200
    )
    assert calls == []
    reader = client.get(path + "?page=3")
    assert "本书选段学习位置" in reader.text and "PDF 第 2 页" in reader.text
    client.post(
        "/web/coach/message", data={**form(client), "message": "请解释这个知识点"}
    )
    assert len(calls) == 1 and calls[0]["sources"][0]["locator"].startswith(
        "PDF 第 2 页"
    )


def test_native_pdf_and_text_current_page_preview_do_not_call_ai(setup):
    _, client, _, calls, _ = setup
    _, identity, path, _ = seed(setup)
    native = client.get(path + "/learn?page=6")
    assert native.status_code == 200 and "PDF 第 6 页" in native.text
    _, identity, path, _ = seed(setup, "txt")
    preview = client.get(path + "/learn?page=2")
    assert preview.url.query == b"part=4"
    assert calls == []


@pytest.mark.parametrize(
    "query", ["", "?page=0", "?page=7", "?page=1&page=2", "?page=1&extra=1"]
)
def test_bad_learning_page_does_not_pick_another_page(setup, query):
    _, client, _, calls, _ = setup
    materials, _, path, _ = seed(setup)
    before = materials.database_path.read_bytes()
    assert client.get(path + "/learn" + query).status_code == 400
    assert materials.database_path.read_bytes() == before and calls == []


def test_bookmark_survives_whole_space_backup_restore(setup):
    from coach.local_backup import create_backup, restore_backup

    _, client, user, calls, directory = setup
    _, identity, path, fields = seed(setup, "txt")
    client.post(path + "/position", data=fields)
    (directory / ".coach-mode").write_text("real", encoding="ascii")
    archive = create_backup(
        directory, directory.parent / (directory.name + "-backup.zip")
    )
    target = directory.parent / (directory.name + "-restored")
    restore_backup(archive, target)
    restored = MaterialRepository(target / "coach_library.db")
    assert restored.reading_position(user.user_id, identity) == {
        "page": 2,
        "revision": 1,
    }
    assert calls == []
