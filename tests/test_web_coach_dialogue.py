import smtplib
import sqlite3
import secrets
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from api.account_pages import SESSION_COOKIE
from coach.dialogue import CoachAnswer
from conversation.coach_repository import CoachRepository
from security.email_verification import (
    issue_email_verification,
    confirm_email_verification,
)
from security.passwords import hash_password
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


BASE = "https://coach.example.com"
PASSWORD = "a private growth workspace phrase"
LEARNING = {
    "topic": "时间管理",
    "progress": "讨论了优先级。",
    "next_step": "安排明天的一项任务。",
}


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"path": attrs.get("action"), "values": {}}
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None:
            self.current["values"][attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None

    def values(self, path, action=None):
        return next(
            form["values"]
            for form in self.forms
            if form["path"] == path
            and (action is None or form["values"].get("action") == action)
        )


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("no external mail or AI in tests")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


def add_user(directory, password_hash, email, name):
    repository = SQLiteUserRepository(directory / "users.db")
    user = User(name=name, email=email)
    repository.save(user)
    repository.save_initial_password_hash(user.user_id, password_hash)
    message = issue_email_verification(
        repository, user.user_id, BASE + "/web/verify-email"
    )
    confirm_email_verification(
        repository, parse_qs(urlsplit(message.activation_url).query)["token"][0]
    )
    return user


def login(client, email="one@example.com"):
    csrf = Forms(client.get("/web/login").text).values("/web/auth/login")["csrf"]
    return client.post(
        "/web/auth/login", data={"email": email, "password": PASSWORD, "csrf": csrf}
    )


def form(client, action="message"):
    values = Forms(client.get("/web/welcome").text).values("/web/coach/message", action)
    return {**values, "message": "我想学习时间管理" if action == "message" else ""}


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "成长者")
    calls = []

    def responder(history, message, learning, **kwargs):
        calls.append((history, message, learning))
        return CoachAnswer(
            "<script>不会执行</script>讨论优先级。",
            LEARNING if "学习" in message else None,
        )

    app = create_account_app(
        tmp_path, dialogue_responder=responder, dialogue_label="模拟 AI 测试"
    )
    with TestClient(app, base_url=BASE) as client:
        yield app, client, calls, user, responder


def test_auth_required_and_no_get_request_calls_ai(setup):
    _, client, calls, _, _ = setup
    assert (
        client.post("/web/coach/message", data={}).status_code == 200
    )  # follows login redirect
    assert "登录" in client.get("/web/login").text
    login(client)
    for _ in range(2):
        assert client.get("/web/welcome").status_code == 200
    assert calls == []


def test_send_persist_escape_deduplicate_and_visible_progress(setup):
    _, client, calls, _, _ = setup
    login(client)
    fields = form(client)
    response = client.post("/web/coach/message", data=fields, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/web/welcome#coach-dialog"
    page = client.get(response.headers["location"])
    assert "时间管理" in page.text and "讨论了优先级" in page.text
    assert "安排明天的一项任务" in page.text
    assert "&lt;script&gt;" in page.text and "<script>" not in page.text
    assert "正在引用的书籍资料" in page.text and "未关联资料" in page.text
    assert 'aria-label="学习位置速览"' in page.text
    assert page.text.count('id="latest-reply"') == 1
    assert page.headers["cache-control"] == "no-store"
    assert client.post("/web/coach/message", data=fields).status_code == 200
    assert len(calls) == 1


def test_detour_continue_logout_login_and_restart_keep_same_learning(setup, tmp_path):
    _, client, calls, _, responder = setup
    login(client)
    client.post("/web/coach/message", data=form(client))
    values = form(client)
    client.post("/web/coach/message", data={**values, "message": "今天有点累"})
    assert "时间管理" in client.get("/web/welcome").text
    resume = form(client, "continue")
    client.post("/web/coach/message", data=resume)
    assert calls[-1][1] == "继续上次学习：时间管理"
    assert len(calls[-1][0]) == 4
    logout = Forms(client.get("/web/welcome").text).values("/web/auth/logout")
    client.post("/web/auth/logout", data=logout)
    assert login(client).status_code == 200
    token = client.cookies.get(SESSION_COOKIE)
    restarted = create_account_app(tmp_path, dialogue_responder=responder)
    with TestClient(restarted, base_url=BASE) as fresh:
        fresh.cookies.set(SESSION_COOKIE, token)
        page = fresh.get("/web/welcome")
        assert "时间管理" in page.text and "今天有点累" in page.text
        assert fresh.post("/web/coach/message", data=resume).status_code == 403
        assert len(calls) == 3


def test_second_account_cannot_read_or_continue_first_account_topic(
    setup, tmp_path, password_hash
):
    app, client, calls, user, _ = setup
    login(client)
    stolen = form(client)
    client.post("/web/coach/message", data=stolen)
    add_user(tmp_path, password_hash, "two@example.com", "第二位")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        page = other.get("/web/welcome?user_id=" + user.user_id)
        assert "还没有开始主题学习" in page.text
        assert "讨论了优先级" not in page.text
        assert other.post("/web/coach/message", data=stolen).status_code == 403
        values = form(other)
        result = other.post(
            "/web/coach/message?user_id=" + user.user_id,
            data={**values, "message": "你好"},
        )
        assert result.status_code == 200
    assert (
        len(
            CoachRepository(tmp_path / "coach_conversations.db").view(user.user_id)[
                "turns"
            ]
        )
        == 1
    )
    assert len(calls) == 2


@pytest.mark.parametrize(
    "kind", ["csrf", "action", "nonce", "extra", "cross-site", "origin"]
)
def test_invalid_or_cross_origin_forms_do_not_call_ai(setup, kind):
    _, client, calls, _, _ = setup
    login(client)
    values, headers = form(client), {}
    if kind in {"csrf", "nonce"}:
        values[kind] = "bad"
    elif kind == "action":
        values["action"] = "continue"
    elif kind == "extra":
        values["user_id"] = "other"
    elif kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    else:
        headers["origin"] = "https://attacker.example"
    assert client.post(
        "/web/coach/message", data=values, headers=headers
    ).status_code in {400, 403}
    assert calls == []


@pytest.mark.parametrize("message", ["", "x" * 2001, "中" * 3000])
def test_invalid_message_lengths_do_not_call_ai(setup, message):
    _, client, calls, _, _ = setup
    login(client)
    assert (
        client.post(
            "/web/coach/message", data={**form(client), "message": message}
        ).status_code
        == 400
    )
    assert calls == []


def test_chinese_limit_message_can_be_sent_and_rate_limit_cannot_be_bypassed(setup):
    _, client, calls, _, _ = setup
    login(client)
    for i in range(8):
        values = form(client)
        assert (
            client.post(
                "/web/coach/message",
                data={**values, "message": "中" * 2000},
                headers={"x-forwarded-for": str(i)},
            ).status_code
            == 200
        )
    response = client.post("/web/coach/message", data=form(client))
    assert response.status_code == 429 and "retry-after" in response.headers
    assert len(calls) == 8


def test_provider_failure_is_private_and_refresh_does_not_retry(
    tmp_path, password_hash
):
    add_user(tmp_path, password_hash, "one@example.com", "成长者")
    calls = []

    def broken(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("private-api-key")

    app = create_account_app(tmp_path, dialogue_responder=broken)
    with TestClient(app, base_url=BASE) as client:
        login(client)
        response = client.post("/web/coach/message", data=form(client))
        assert (
            "这次未能取得回复" in response.text
            and "private-api-key" not in response.text
        )
        client.get("/web/welcome")
        assert calls == [True]


def test_database_read_failure_is_sanitized(setup, monkeypatch):
    _, client, _, _, _ = setup
    login(client)

    def broken(*a, **k):
        raise sqlite3.OperationalError("private database path")

    monkeypatch.setattr(CoachRepository, "view", broken)
    response = client.get("/web/welcome")
    assert response.status_code == 503 and "private database path" not in response.text


def test_clean_layout_has_scrolling_history_and_moves_help_to_learning_panel(setup):
    _, client, _, _, _ = setup
    page = login(client)
    assert 'id="dialogue-history"' in page.text
    assert 'src="/static/coach-dialogue.js"' in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert "connect-src 'self'" in page.headers["content-security-policy"]
    for removed in (
        "你的账户已经准备好",
        "此处显示最近",
        "查看较早的对话",
        'class="conversation-heading"',
    ):
        assert removed not in page.text
    middle = page.text.split('id="coach-dialog"', 1)[1].split("</section>", 1)[0]
    assert "模拟 AI 测试" not in middle and "知识成果保存功能准备中" not in middle
    assert "对话记录与使用说明" in page.text
    assert client.get("/static/coach-dialogue.js").status_code == 200


def test_history_api_paginates_without_ai_calls(setup, tmp_path):
    _, client, calls, user, _ = setup
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    for index in range(83):
        nonce = secrets.token_urlsafe(32)
        repo.claim(user.user_id, nonce, f"本人记录{index}", now=1000 + index)
        repo.finish(
            user.user_id, nonce, "<script>安全文本</script>", None, now=1000 + index
        )
    login(client)
    first = repo.view(user.user_id)
    response = client.get("/web/coach/history", params={"before": first["before"]})
    assert (
        response.status_code == 200 and response.headers["cache-control"] == "no-store"
    )
    second = response.json()
    assert (
        len(second["turns"]) == 40 and second["turns"][0]["user_content"] == "本人记录3"
    )
    oldest = client.get(
        "/web/coach/history", params={"before": second["before"]}
    ).json()
    assert len(oldest["turns"]) == 3 and oldest["before"] is None
    assert oldest["turns"][0]["user_content"] == "本人记录0"
    assert calls == []


def test_history_requires_login_and_uses_current_account(
    setup, tmp_path, password_hash
):
    app, client, _, user, _ = setup
    assert client.get("/web/coach/history?before=2").status_code == 401
    login(client)
    client.post("/web/coach/message", data=form(client))
    add_user(tmp_path, password_hash, "two@example.com", "第二位")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        response = other.get("/web/coach/history?before=100")
        assert response.json() == {"turns": [], "before": None}
        assert "时间管理" not in response.text and user.user_id not in response.text
        assert (
            other.get(
                "/web/coach/history?before=100&user_id=" + user.user_id
            ).status_code
            == 400
        )


@pytest.mark.parametrize(
    "query",
    [
        "",
        "before=-1",
        "before=0",
        "before=x",
        "before=1&before=2",
        "before=9223372036854775808",
    ],
)
def test_invalid_history_query_rejected(setup, query):
    _, client, calls, _, _ = setup
    login(client)
    assert client.get("/web/coach/history?" + query).status_code == 400
    assert calls == []


def test_history_origin_limits_and_database_failures_are_safe(setup, monkeypatch):
    _, client, calls, _, _ = setup
    login(client)
    path = "/web/coach/history?before=100"
    assert client.get(path, headers={"sec-fetch-site": "cross-site"}).status_code == 403

    def broken(*a, **k):
        raise sqlite3.OperationalError("private data path")

    with monkeypatch.context() as patch:
        patch.setattr(CoachRepository, "history_page", broken)
        response = client.get(path)
        assert response.status_code == 503 and "private data path" not in response.text
    for i in range(29):
        assert client.get(path, headers={"x-forwarded-for": str(i)}).status_code == 200
    response = client.get(path)
    assert response.status_code == 429 and "retry-after" in response.headers
    assert calls == []
