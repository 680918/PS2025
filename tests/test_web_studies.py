import secrets
import smtplib
from time import time

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from coach.dialogue import CoachAnswer
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_web_coach_dialogue import add_user, login, Forms, PASSWORD, BASE


@pytest.fixture(autouse=True)
def no_paid_services(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("No real SMTP or AI")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "续学体验者")
    other = add_user(tmp_path, password_hash, "two@example.com", "其他用户")
    calls = []

    def responder(history, message, learning, *, context):
        calls.append((history, message, learning, context))
        return CoachAnswer(
            "接着主题继续讨论。",
            {
                "topic": "模型不能改续学名称",
                "progress": "接着上次讨论",
                "next_step": "结合一个例子",
            },
        )

    app = create_account_app(tmp_path, dialogue_responder=responder)
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    materials = MaterialRepository(tmp_path / "coach_library.db")
    with TestClient(app, base_url=BASE) as client:
        yield app, client, repo, materials, user, other, calls


def create(client, title, material_id=""):
    fields = Forms(client.get("/web/studies").text).values("/web/studies/new")
    return client.post(
        "/web/studies/new", data={**fields, "title": title, "material_id": material_id}
    )


def choose(client, identity, operation):
    path = f"/web/studies/{identity}/{operation}"
    fields = Forms(client.get("/web/studies").text).values(path)
    return client.post(path, data=fields)


def test_create_switch_resume_and_per_topic_book_restore(setup):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    a_book = materials.add(user.user_id, "a.txt", "变量与循环".encode())
    b_book = materials.add(user.user_id, "b.txt", "阅读提问".encode())
    assert create(client, "Python 入门", a_book).status_code == 200
    a = repo.active_topic(user.user_id)["topic_id"]
    assert create(client, "阅读方法", b_book).status_code == 200
    b = repo.active_topic(user.user_id)["topic_id"]
    assert calls == []
    assert choose(client, a, "open").status_code == 200 and calls == []
    assert repo.active_topic(user.user_id)["topic_id"] == a
    reply = choose(client, b, "continue")
    assert (
        reply.status_code == 200 and "我们回到「阅读方法」学习主题上来。" in reply.text
    )
    assert calls[0][3]["material"]["material_id"] == b_book
    assert repo.active_topic(user.user_id)["title"] == "阅读方法"
    assert repo.topic(user.user_id, a)["material_id"] == a_book
    assert "我的学习" in client.get("/web/welcome").text


def test_resume_replay_is_idempotent_and_csrf_is_bound_to_target_and_session(setup):
    app, client, repo, _, user, _, calls = setup
    login(client)
    create(client, "主题A")
    a = repo.active_topic(user.user_id)["topic_id"]
    create(client, "主题B")
    b = repo.active_topic(user.user_id)["topic_id"]
    path = f"/web/studies/{a}/continue"
    fields = Forms(client.get("/web/studies").text).values(path)
    assert client.post(f"/web/studies/{b}/continue", data=fields).status_code == 403
    with TestClient(app, base_url=BASE) as other:
        login(other)
        assert other.post(path, data=fields).status_code == 403
    assert client.post(path, data=fields).status_code == 200
    assert client.post(path, data=fields).status_code == 200 and len(calls) == 1


@pytest.mark.parametrize(
    "kind", ["csrf", "origin", "cross-site", "user-id", "duplicate", "json", "oversize"]
)
def test_topic_creation_rejects_bad_or_forged_forms(setup, kind):
    _, client, repo, _, user, _, calls = setup
    login(client)
    fields = Forms(client.get("/web/studies").text).values("/web/studies/new")
    fields.update(title="测试主题", material_id="")
    headers = {}
    if kind == "csrf":
        fields["csrf"] = "中" * 64
    if kind == "origin":
        headers["origin"] = "https://outside.example"
    if kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "user-id":
        fields["user_id"] = user.user_id
    if kind == "oversize":
        fields["title"] = "字" * 5000
    if kind == "duplicate":
        result = client.post(
            "/web/studies/new",
            content="csrf=x&csrf=y&title=a&material_id=",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    elif kind == "json":
        result = client.post("/web/studies/new", json=fields)
    else:
        result = client.post("/web/studies/new", data=fields, headers=headers)
    assert (
        result.status_code in (400, 403)
        and repo.list_topics(user.user_id) == []
        and calls == []
    )


def test_ownership_busy_guards_and_no_get_calls_ai(setup):
    _, client, repo, materials, user, other, calls = setup
    assert client.get("/web/studies", follow_redirects=False).status_code == 303
    login(client)
    repo.create_topic(user.user_id, "本人主题")
    own = repo.active_topic(user.user_id)["topic_id"]
    repo.create_topic(other.user_id, "other-private-theme")
    other_book = materials.add(other.user_id, "private.txt", b"private")
    assert (
        "other-private-theme"
        not in client.get("/web/studies?user_id=" + other.user_id).text
    )
    assert create(client, "错误资料", other_book).status_code == 404
    path = f"/web/studies/{own}/open"
    fields = Forms(client.get("/web/studies").text).values(path)
    repo.claim(user.user_id, secrets.token_urlsafe(32), "未结束的消息", now=int(time()))
    assert client.post(path, data=fields).status_code == 409
    assert create(client, "另一个主题").status_code == 409
    assert calls == []


def test_disabled_ai_still_allows_navigation_and_search_pagination(setup):
    _, _, repo, _, user, _, _ = setup
    for i in range(13):
        repo.create_topic(user.user_id, f"主题{i:02d}", now=1000 + i)
    app = create_account_app(repo.database_path.parent)
    with TestClient(app, base_url=BASE) as client:
        login(client)
        first = client.get("/web/studies")
        assert "下一页" in first.text
        assert "主题00" in client.get("/web/studies?page=2").text
        search = client.get("/web/studies?q=主题00")
        assert "主题00" in search.text and "主题12" not in search.text
        identity = repo.list_topics(user.user_id, query="主题00")[0]["topic_id"]
        open_path = f"/web/studies/{identity}/open"
        assert (
            client.post(
                open_path, data=Forms(search.text).values(open_path)
            ).status_code
            == 200
        )
        path = f"/web/studies/{identity}/continue"
        fields = Forms(client.get("/web/studies?q=主题00").text).values(path)
        assert client.post(path, data=fields).status_code == 503


def test_opaque_same_origin_forms_and_escaping_are_supported(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    fields = Forms(client.get("/web/studies").text).values("/web/studies/new")
    result = client.post(
        "/web/studies/new",
        data={**fields, "title": "<script>主题</script>", "material_id": ""},
        headers={"origin": "null", "sec-fetch-site": "same-origin"},
    )
    assert result.status_code == 200
    directory = client.get("/web/studies")
    assert (
        "&lt;script&gt;主题&lt;/script&gt;" in directory.text
        and "<script>主题" not in directory.text
    )
    assert directory.headers["cache-control"] == "no-store" and calls == []


def test_old_workspace_form_resumes_its_displayed_topic_and_csrf_binds_identity(setup):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    book = materials.add(user.user_id, "python.txt", b"variables")
    create(client, "Python 入门", book)
    a = repo.active_topic(user.user_id)["topic_id"]
    fields = Forms(client.get("/web/welcome").text).values(
        "/web/coach/message", "message"
    )
    assert fields["study_id"] == a
    create(client, "阅读方法")
    b = repo.active_topic(user.user_id)["topic_id"]
    assert (
        client.post(
            "/web/coach/message", data={**fields, "message": "继续变量", "study_id": b}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/web/coach/message", data={**fields, "message": "继续变量"}
        ).status_code
        == 200
    )
    assert calls[0][2]["topic"] == "Python 入门"
    assert calls[0][3]["material"]["material_id"] == book
    assert repo.topic(user.user_id, b)["progress"] == "尚未开始讨论。"
