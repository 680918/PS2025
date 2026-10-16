import sqlite3
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from api import email_verification_pages as pages
from api.app import create_app
from security.email_verification import issue_email_verification
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


class FormInputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.values[attrs["name"]] = attrs["value"]


@pytest.fixture
def account(tmp_path):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="临时测试者", email="learner@example.com")
    repository.save(user)
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app, base_url="https://coach.example.com") as client:
        yield repository, user, client


def issue(repository, user, *, now=None):
    message = issue_email_verification(
        repository, user.user_id, "https://coach.example.com/web/verify-email", now=now
    )
    return message.activation_url


def open_form(client, link):
    page = client.get(link)
    assert page.status_code == 200
    return FormInputs(page.text).values


def test_get_head_and_prefetch_never_consume_then_post_verifies_once(account):
    repository, user, client = account
    link = issue(repository, user)
    before = repository.get_by_id(user.user_id)
    for headers in [{}, {"Purpose": "prefetch"}, {"Sec-Purpose": "prefetch"}]:
        page = client.get(link, headers=headers)
        assert "确认这是你的邮箱" in page.text
        assert "确认验证邮箱" in page.text
        assert not repository.is_email_verified(user.user_id)
    client.head(link)
    assert not repository.is_email_verified(user.user_id)
    form = open_form(client, link)
    result = client.post("/web/verify-email", data=form)
    assert result.status_code == 200
    assert "邮箱验证成功" in result.text
    assert "登录功能正在准备中" in result.text
    assert "自动登录" in result.text
    assert user.email not in result.text
    assert user.user_id not in result.text
    assert form["token"] not in result.text
    assert repository.is_email_verified(user.user_id)
    assert repository.get_by_id(user.user_id) == before
    assert repository.get_password_hash(user.user_id) is None
    assert not client.cookies
    repeated = client.post("/web/verify-email", data=open_form(client, link))
    assert repeated.status_code == 400
    assert "这个验证链接暂时无法使用" in repeated.text
    assert repository.is_email_verified(user.user_id)


@pytest.mark.parametrize("kind", ["expired", "superseded", "changed-email", "unknown"])
def test_invalid_links_have_same_result_and_never_verify(account, kind):
    repository, user, client = account
    now = datetime.now(timezone.utc)
    link = issue(
        repository,
        user,
        now=now - timedelta(hours=2)
        if kind == "expired"
        else now - timedelta(minutes=2),
    )
    if kind == "superseded":
        issue(repository, user)
    elif kind == "changed-email":
        with sqlite3.connect(repository.database_path) as connection:
            connection.execute(
                "UPDATE users SET email=? WHERE user_id=?",
                ("changed@example.com", user.user_id),
            )
    elif kind == "unknown":
        link = "/web/verify-email?token=" + "a" * 43
    result = client.post("/web/verify-email", data=open_form(client, link))
    assert result.status_code == 400
    assert "这个验证链接暂时无法使用" in result.text
    assert "查看注册页" in result.text
    assert not repository.is_email_verified(user.user_id)


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?token=bad",
        "?token=" + "a" * 44,
        "?token=%3Cscript%3Ealert(1)%3C/script%3E",
        "?token=" + "a" * 43 + "&token=" + "b" * 43,
    ],
)
def test_malformed_get_does_not_echo_input_or_set_cookie(account, query):
    repository, user, client = account
    page = client.get("/web/verify-email" + query)
    assert page.status_code == 400
    assert "<script>" not in page.text
    assert "<form" not in page.text
    assert "set-cookie" not in page.headers
    assert not repository.is_email_verified(user.user_id)


@pytest.mark.parametrize(
    "case",
    [
        "missing-cookie",
        "tampered-cookie",
        "wrong-csrf",
        "wrong-token",
        "stale-tab",
        "expired-form",
    ],
)
def test_submission_needs_signed_browser_confirmation(account, monkeypatch, case):
    repository, user, client = account
    link = issue(repository, user)
    form = open_form(client, link)
    if case == "missing-cookie":
        client.cookies.clear()
    elif case == "tampered-cookie":
        cookie = client.cookies.get(pages._COOKIE)
        client.cookies.clear()
        client.cookies.set(
            pages._COOKIE, cookie[:-1] + ("1" if cookie[-1] != "1" else "2")
        )
    elif case == "wrong-csrf":
        form["csrf"] = "a" * 43
    elif case == "wrong-token":
        form["token"] = "a" * 43
    elif case == "stale-tab":
        open_form(client, link)
    elif case == "expired-form":
        later = pages.time() + 601
        monkeypatch.setattr(pages, "time", lambda: later)
    result = client.post("/web/verify-email", data=form)
    assert result.status_code == 403
    assert "请重新打开验证邮件" in result.text
    assert not repository.is_email_verified(user.user_id)


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://other.example"},
        {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_post_cannot_verify_even_with_form(account, headers):
    repository, user, client = account
    form = open_form(client, issue(repository, user))
    result = client.post("/web/verify-email", data=form, headers=headers)
    assert result.status_code == 403
    assert not repository.is_email_verified(user.user_id)


def test_same_origin_form_submission_works(account):
    repository, user, client = account
    result = client.post(
        "/web/verify-email",
        data=open_form(client, issue(repository, user)),
        headers={
            "Origin": "https://coach.example.com",
            "Sec-Fetch-Site": "same-origin",
        },
    )
    assert result.status_code == 200


def test_privacy_protected_null_origin_requires_valid_signed_confirmation(account):
    repository, user, client = account
    link = issue(repository, user)
    form = open_form(client, link)
    assert (
        client.post(
            "/web/verify-email", data=form, headers={"Origin": "null"}
        ).status_code
        == 200
    )
    assert repository.is_email_verified(user.user_id)


def test_null_origin_without_confirmation_cookie_cannot_verify(account):
    repository, user, client = account
    form = open_form(client, issue(repository, user))
    client.cookies.clear()
    assert (
        client.post(
            "/web/verify-email", data=form, headers={"Origin": "null"}
        ).status_code
        == 403
    )
    assert not repository.is_email_verified(user.user_id)


@pytest.mark.parametrize(
    "body,content_type",
    [
        ('{"token":"secret-test-only"}', "application/json"),
        ("token=secret-test-only", "application/x-www-form-urlencoded"),
        (
            "token=" + "a" * 43 + "&csrf=" + "b" * 43 + "&csrf=x",
            "application/x-www-form-urlencoded",
        ),
        ("token=%FF&csrf=a", "application/x-www-form-urlencoded"),
        ("token=" + "x" * 3000, "application/x-www-form-urlencoded"),
    ],
)
def test_bad_posts_are_small_html_errors_without_input_echo(
    account, body, content_type
):
    repository, user, client = account
    result = client.post(
        "/web/verify-email", content=body, headers={"Content-Type": content_type}
    )
    assert result.status_code == 400
    assert "text/html" in result.headers["Content-Type"]
    assert "secret-test-only" not in result.text
    assert not repository.is_email_verified(user.user_id)


def test_confirmation_is_scoped_cookie_not_login_and_pages_do_not_leak_referrers(
    account,
):
    repository, user, client = account
    response = client.get(issue(repository, user))
    cookie = response.headers["set-cookie"]
    for flag in [
        "HttpOnly",
        "Secure",
        "SameSite=strict",
        "Path=/web/verify-email",
        "Max-Age=600",
    ]:
        assert flag in cookie
    for page in [response, client.get("/web/verify-email")]:
        assert page.headers["cache-control"] == "no-store"
        assert page.headers["referrer-policy"] == "no-referrer"
        assert page.headers["x-frame-options"] == "DENY"
        assert "form-action 'self'" in page.headers["content-security-policy"]
        assert "<script" not in page.text
        assert "<iframe" not in page.text
        assert "https://" not in page.text


def test_storage_failure_is_retryable_without_exposing_details(account, monkeypatch):
    repository, user, client = account
    link = issue(repository, user)
    form = open_form(client, link)
    real_confirm = pages.confirm_email_verification

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("private-file-location-and-token")

    monkeypatch.setattr(pages, "confirm_email_verification", fail)
    result = client.post("/web/verify-email", data=form)
    assert result.status_code == 503
    assert "验证暂时无法完成" in result.text
    assert "private-file" not in result.text
    assert not repository.is_email_verified(user.user_id)
    monkeypatch.setattr(pages, "confirm_email_verification", real_confirm)
    assert client.post("/web/verify-email", data=form).status_code == 200


def test_restart_requires_reopening_mail_but_keeps_verification_token(
    account, tmp_path
):
    repository, user, client = account
    link = issue(repository, user)
    old_form = open_form(client, link)
    old_cookie = client.cookies.get(pages._COOKIE)
    restarted = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(restarted, base_url="https://coach.example.com") as other:
        other.cookies.set(pages._COOKIE, old_cookie)
        assert other.post("/web/verify-email", data=old_form).status_code == 403
        other.cookies.clear()
        assert (
            other.post("/web/verify-email", data=open_form(other, link)).status_code
            == 200
        )
    assert repository.is_email_verified(user.user_id)


def test_http_loopback_confirmation_can_work_without_secure_cookie(tmp_path):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="临时测试者", email="learner@example.com")
    repository.save(user)
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        message = issue_email_verification(
            repository, user.user_id, "http://127.0.0.1:8000/web/verify-email"
        )
        response = client.get(message.activation_url)
        assert "Secure" not in response.headers["set-cookie"]
        assert (
            client.post(
                "/web/verify-email",
                data=FormInputs(response.text).values,
                headers={"Origin": "http://127.0.0.1:8000"},
            ).status_code
            == 200
        )
