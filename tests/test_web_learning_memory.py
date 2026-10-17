import io
import smtplib
import sqlite3
from zipfile import ZipFile

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from coach.dialogue import simulated_responder
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_web_coach_dialogue import add_user, login, form, Forms, PASSWORD, BASE


@pytest.fixture(autouse=True)
def no_paid_services(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("no real SMTP or AI")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "记忆体验者")
    other = add_user(tmp_path, password_hash, "two@example.com", "另一个用户")
    app = create_account_app(tmp_path, dialogue_responder=simulated_responder)
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    with TestClient(app, base_url=BASE) as client:
        yield app, client, repo, user, other


def add(client, content):
    fields = Forms(client.get("/web/memories").text).values("/web/memories/add")
    return client.post("/web/memories/add", data={**fields, "content": content})


def test_chat_save_edit_resume_delete_and_export_are_connected(setup):
    _, client, repo, user, _ = setup
    welcome = login(client)
    assert "/web/memories" in welcome.text
    reply = client.post(
        "/web/coach/message", data={**form(client), "message": "请记住，我喜欢先看例子"}
    )
    assert "已记住" in reply.text and "我喜欢先看例子" in reply.text
    note = repo.list_memories(user.user_id)[0]
    path = "/web/memories/" + note["memory_id"]
    editor = client.get(path)
    assert "我喜欢先看例子" in editor.text
    changed = client.post(
        path, data={**Forms(editor.text).values(path), "content": "我喜欢一步一步讲解"}
    )
    assert "已修改" in changed.text
    reply = client.post(
        "/web/coach/message", data={**form(client), "message": "解释变量"}
    )
    assert "一步一步讲解" in reply.text
    export = client.get("/web/export")
    result = client.post(
        "/web/export",
        data={
            **Forms(export.text).values("/web/export"),
            "period": "all",
            "scope": ["memories"],
        },
    )
    assert result.status_code == 200
    with ZipFile(io.BytesIO(result.content)) as zipped:
        assert "一步一步讲解" in zipped.read("学习记忆/记录/我的学习记忆.txt").decode()
    confirm = client.get(path + "/delete")
    assert len(repo.list_memories(user.user_id)) == 1
    deleted = client.post(
        path + "/delete", data=Forms(confirm.text).values(path + "/delete")
    )
    assert "长期记忆已删除" in deleted.text and repo.list_memories(user.user_id) == []
    assert client.get(path).status_code == 404


def test_manual_add_duplicate_and_restart_preserve_memory_without_ai(setup):
    _, client, repo, user, _ = setup
    login(client)
    assert "还没有" not in add(client, "我的学习目标是理解 Python").text
    assert "无需重复" in add(client, "我的学习目标是理解 Python").text
    restarted = create_account_app(repo.database_path.parent)
    with TestClient(restarted, base_url=BASE) as fresh:
        login(fresh)
        assert "理解 Python" in fresh.get("/web/memories").text
    assert len(repo.list_memories(user.user_id)) == 1


def test_authentication_ownership_and_html_escape(setup):
    app, client, repo, user, other = setup
    assert client.get("/web/memories", follow_redirects=False).status_code == 303
    login(client)
    repo.add_memory(user.user_id, "<script>test</script>")
    repo.add_memory(other.user_id, "other-private-note")
    other_note = repo.list_memories(other.user_id)[0]
    assert "&lt;script&gt;test&lt;/script&gt;" in client.get("/web/memories").text
    assert (
        "other-private-note"
        not in client.get("/web/memories?user_id=" + other.user_id).text
    )
    assert client.get("/web/memories/" + other_note["memory_id"]).status_code == 404
    assert (
        client.get("/web/memories/" + other_note["memory_id"] + "/delete").status_code
        == 404
    )
    page = client.get("/web/memories")
    assert (
        page.headers["cache-control"] == "no-store"
        and page.headers["referrer-policy"] == "no-referrer"
    )


@pytest.mark.parametrize(
    "kind", ["csrf", "origin", "cross-site", "null", "user-id", "oversize", "json"]
)
def test_add_rejects_forged_cross_site_or_malformed_requests(setup, kind):
    _, client, repo, user, _ = setup
    login(client)
    fields = Forms(client.get("/web/memories").text).values("/web/memories/add")
    fields["content"] = "我的目标"
    headers = {}
    if kind == "csrf":
        fields["csrf"] = "中" * 64
    if kind == "origin":
        headers["origin"] = "https://outside.example"
    if kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "null":
        headers["origin"] = "null"
    if kind == "user-id":
        fields["user_id"] = user.user_id
    if kind == "oversize":
        fields["content"] = "字" * 5000
    result = (
        client.post("/web/memories/add", json=fields)
        if kind == "json"
        else client.post("/web/memories/add", data=fields, headers=headers)
    )
    assert result.status_code in (400, 403) and repo.list_memories(user.user_id) == []


def test_cross_session_csrf_and_stale_revision_cannot_modify_or_delete(setup):
    app, client, repo, user, _ = setup
    login(client)
    add(client, "旧偏好")
    note = repo.list_memories(user.user_id)[0]
    path = "/web/memories/" + note["memory_id"]
    edit_fields = Forms(client.get(path).text).values(path)
    delete_fields = Forms(client.get(path + "/delete").text).values(path + "/delete")
    with TestClient(app, base_url=BASE) as stranger:
        login(stranger)
        assert (
            stranger.post(
                path, data={**edit_fields, "content": "跨会话修改"}
            ).status_code
            == 403
        )
    assert (
        client.post(path, data={**edit_fields, "content": "新偏好"}).status_code == 200
    )
    stale = client.post(path, data={**edit_fields, "content": "另一页未保存的填写"})
    assert (
        stale.status_code == 409
        and "新偏好" in stale.text
        and "未保存的填写" in stale.text
    )
    assert client.post(path + "/delete", data=delete_fields).status_code == 409
    assert repo.list_memories(user.user_id)[0]["content"] == "新偏好"


def test_invalid_content_and_database_errors_are_clear_and_do_not_echo_details(
    setup, monkeypatch
):
    _, client, repo, user, _ = setup
    login(client)
    for text in (" ", "字" * 301, "密码是abc123"):
        assert add(client, text).status_code == 400

    def broken(*a, **k):
        raise sqlite3.OperationalError("private-database-details")

    monkeypatch.setattr(
        "conversation.coach_repository.CoachRepository.add_memory", broken
    )
    result = add(client, "新的目标")
    assert result.status_code == 503 and "private-database-details" not in result.text
    assert repo.list_memories(user.user_id) == []


def test_all_five_export_scopes_are_accepted_and_no_scope_is_silently_dropped(setup):
    _, client, repo, user, _ = setup
    login(client)
    add(client, "我的学习目标")
    fields = Forms(client.get("/web/export").text).values("/web/export")
    result = client.post(
        "/web/export",
        data={
            **fields,
            "period": "all",
            "scope": ["saved", "drafts", "chat", "materials", "memories"],
        },
    )
    assert result.status_code == 200
    with ZipFile(io.BytesIO(result.content)) as zipped:
        assert "学习记忆/记录/我的学习记忆.txt" in zipped.namelist()


def test_embedded_browser_opaque_origin_still_requires_same_origin_metadata_and_csrf(
    setup,
):
    _, client, repo, user, _ = setup
    login(client)
    fields = Forms(client.get("/web/memories").text).values("/web/memories/add")
    fields["content"] = "我喜欢具体的例子"
    headers = {"origin": "null", "sec-fetch-site": "same-origin"}
    accepted = client.post("/web/memories/add", data=fields, headers=headers)
    assert accepted.status_code == 200 and len(repo.list_memories(user.user_id)) == 1
    forged = client.post(
        "/web/memories/add",
        data={**fields, "csrf": "a" * 64, "content": "伪造内容"},
        headers=headers,
    )
    assert forged.status_code == 403
    cross_site = client.post(
        "/web/memories/add",
        data=fields,
        headers={"origin": "null", "sec-fetch-site": "cross-site"},
    )
    assert cross_site.status_code == 403
