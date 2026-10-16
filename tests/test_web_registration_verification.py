import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api import email_verification_pages as pages
from api.app import create_app
from security.auth import initialize_user_password, verify_user_password
from security.email_verification import (
    issue_email_verification,
    issue_registration_verification,
)
from security.pending_registration import begin_pending_registration
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


PATH = "/web/verify-registration"
BASE = "https://coach.example.com"
COOKIE = pages._REGISTRATION_COOKIE
PASSWORD = " a quiet registration phrase "


class ConfirmationForm(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.action = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.action = attrs.get("action")
        if tag == "input":
            self.values[attrs["name"]] = attrs.get("value", "")


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("registration confirmation must not send email")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)


def make_app(directory):
    return create_app(
        directory,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )


@pytest.fixture
def account(tmp_path):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    with TestClient(make_app(tmp_path), base_url=BASE) as client:
        yield repository, client


def issue(repository, *, now=None):
    receipt = begin_pending_registration(
        repository,
        name="测试成长者",
        email="learner@example.com",
        password=PASSWORD,
        now=now,
    )
    message = issue_registration_verification(
        repository, receipt.request_id, BASE + PATH, now=now
    )
    return receipt, message.activation_url


def open_form(client, link):
    response = client.get(link)
    assert response.status_code == 200
    form = ConfirmationForm(response.text)
    assert form.action == PATH
    return form.values


def counts(repository):
    with sqlite3.connect(repository.database_path) as connection:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "users",
                "user_passwords",
                "user_email_verifications",
                "pending_registrations",
                "registration_email_verifications",
            )
        )


def test_get_prefetch_and_head_never_create_then_confirmation_creates_once(account):
    repository, client = account
    receipt, link = issue(repository)
    before = counts(repository)
    assert before == (0, 0, 0, 1, 1)
    for headers in ({}, {"Purpose": "prefetch"}, {"Sec-Purpose": "prefetch"}):
        response = client.get(link, headers=headers)
        assert response.status_code == 200
        assert "确认邮箱，开启成长的第一步" in response.text
        assert "如果这不是你的操作，直接关闭页面" in response.text
        assert counts(repository) == before
    client.head(link)
    assert counts(repository) == before
    form = open_form(client, link)
    result = client.post(PATH, data=form)
    assert result.status_code == 200
    assert "账户已创建，邮箱已验证" in result.text
    assert "登录功能正在准备中" in result.text
    assert "不会自动登录" in result.text
    user = repository.get_by_email("learner@example.com")
    assert user is not None
    assert repository.is_email_verified(user.user_id)
    assert verify_user_password(repository, user.user_id, PASSWORD)
    assert counts(repository) == (1, 1, 1, 0, 0)
    for value in (
        user.email,
        user.user_id,
        receipt.request_id,
        form["token"],
        PASSWORD,
        "$argon2id$",
    ):
        assert value not in result.text
    assert not client.cookies
    assert client.post(PATH, data=form).status_code == 403
    repeated = client.post(PATH, data=open_form(client, link))
    assert repeated.status_code == 400
    assert "这个注册链接暂时无法使用" in repeated.text
    assert counts(repository) == (1, 1, 1, 0, 0)


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?token=bad",
        "?token=" + "a" * 44,
        "?token=%3Cscript%3E",
        "?token=" + "a" * 43 + "&token=" + "b" * 43,
    ],
)
def test_bad_get_is_generic_html_without_cookie_or_input_echo(account, query):
    repository, client = account
    page = client.get(PATH + query)
    assert page.status_code == 400
    assert "这个注册链接暂时无法使用" in page.text
    assert "<script" not in page.text
    assert "<form" not in page.text
    assert "set-cookie" not in page.headers
    assert counts(repository) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "kind", ["expired", "superseded", "unknown", "deleted", "existing-account"]
)
def test_unavailable_links_never_create_or_replace_accounts(account, kind):
    repository, client = account
    now = datetime.now(timezone.utc)
    issued_at = (
        now - timedelta(hours=2) if kind == "expired" else now - timedelta(minutes=2)
    )
    receipt, link = issue(repository, now=issued_at)
    original = None
    if kind == "superseded":
        issue_registration_verification(repository, receipt.request_id, BASE + PATH)
    elif kind == "unknown":
        link = PATH + "?token=" + "a" * 43
    elif kind == "deleted":
        with repository._connect() as connection:
            connection.execute("DELETE FROM pending_registrations")
    elif kind == "existing-account":
        original = User(name="原账户", email=" LEARNER@EXAMPLE.COM ")
        repository.save(original)
        initialize_user_password(
            repository, original.user_id, "original account password"
        )
        original_hash = repository.get_password_hash(original.user_id)
    result = client.post(PATH, data=open_form(client, link))
    assert result.status_code == 400
    assert "这个注册链接暂时无法使用" in result.text
    assert not client.cookies
    if original is None:
        assert repository.get_by_email("learner@example.com") is None
        assert counts(repository)[:3] == (0, 0, 0)
    else:
        assert repository.get_by_id(original.user_id) == original
        assert repository.get_password_hash(original.user_id) == original_hash
        assert not repository.is_email_verified(original.user_id)
        assert counts(repository)[:3] == (1, 1, 0)


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
def test_confirmation_requires_signed_browser_context(account, monkeypatch, case):
    repository, client = account
    _, link = issue(repository)
    form = open_form(client, link)
    if case == "missing-cookie":
        client.cookies.clear()
    elif case == "tampered-cookie":
        cookie = client.cookies.get(COOKIE)
        client.cookies.clear()
        client.cookies.set(COOKIE, cookie[:-1] + ("1" if cookie[-1] != "1" else "2"))
    elif case == "wrong-csrf":
        form["csrf"] = "a" * 43
    elif case == "wrong-token":
        form["token"] = "a" * 43
    elif case == "stale-tab":
        open_form(client, link)
    elif case == "expired-form":
        later = pages.time() + 601
        monkeypatch.setattr(pages, "time", lambda: later)
    result = client.post(PATH, data=form)
    assert result.status_code == 403
    assert "请重新打开注册验证邮件" in result.text
    assert counts(repository) == (0, 0, 0, 1, 1)


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://other.example"},
        {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_post_is_rejected_before_creating(account, headers):
    repository, client = account
    _, link = issue(repository)
    result = client.post(PATH, data=open_form(client, link), headers=headers)
    assert result.status_code == 403
    assert counts(repository) == (0, 0, 0, 1, 1)


@pytest.mark.parametrize("origin", [BASE, "null"])
def test_browser_origin_with_signed_context_can_confirm(account, origin):
    repository, client = account
    _, link = issue(repository)
    result = client.post(
        PATH,
        data=open_form(client, link),
        headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"},
    )
    assert result.status_code == 200
    assert counts(repository) == (1, 1, 1, 0, 0)


@pytest.mark.parametrize(
    "body,content_type",
    [
        ('{"token":"private-test-only"}', "application/json"),
        ("token=private-test-only", "application/x-www-form-urlencoded"),
        (
            "token=" + "a" * 43 + "&csrf=" + "b" * 43 + "&csrf=x",
            "application/x-www-form-urlencoded",
        ),
        ("token=%FF&csrf=a", "application/x-www-form-urlencoded"),
        ("token=" + "x" * 3000, "application/x-www-form-urlencoded"),
    ],
)
def test_bad_posts_are_bounded_generic_html_without_echo(account, body, content_type):
    repository, client = account
    result = client.post(PATH, content=body, headers={"Content-Type": content_type})
    assert result.status_code == 400
    assert "text/html" in result.headers["content-type"]
    assert "private-test-only" not in result.text
    assert counts(repository) == (0, 0, 0, 0, 0)


def test_privacy_headers_and_cookie_scope_without_login(account):
    repository, client = account
    _, link = issue(repository)
    response = client.get(link)
    cookie = response.headers["set-cookie"]
    for flag in [
        "HttpOnly",
        "Secure",
        "SameSite=strict",
        "Path=" + PATH,
        "Max-Age=600",
    ]:
        assert flag in cookie
    for page in (response, client.get(PATH)):
        assert page.headers["cache-control"] == "no-store"
        assert page.headers["referrer-policy"] == "no-referrer"
        assert page.headers["x-frame-options"] == "DENY"
        assert "form-action 'self'" in page.headers["content-security-policy"]
        assert "<script" not in page.text
        assert "<iframe" not in page.text
        assert "https://" not in page.text
    assert set(client.cookies.keys()) == {COOKIE}


def test_real_storage_failure_is_generic_and_same_form_can_retry(account):
    repository, client = account
    _, link = issue(repository)
    form = open_form(client, link)
    with repository._connect() as connection:
        connection.execute(
            "CREATE TRIGGER fail_registration BEFORE INSERT ON user_passwords "
            "BEGIN SELECT RAISE(ABORT, 'private-test-only-db-location'); END"
        )
    result = client.post(PATH, data=form)
    assert result.status_code == 503
    assert "账户创建暂时无法完成" in result.text
    assert "private-test-only" not in result.text
    assert form["token"] not in result.text
    assert counts(repository) == (0, 0, 0, 1, 1)
    with repository._connect() as connection:
        connection.execute("DROP TRIGGER fail_registration")
    assert client.post(PATH, data=form).status_code == 200
    assert counts(repository) == (1, 1, 1, 0, 0)


def test_restart_needs_reopen_but_preserves_registration(account, tmp_path):
    repository, client = account
    _, link = issue(repository)
    old_form = open_form(client, link)
    old_cookie = client.cookies.get(COOKIE)
    with TestClient(make_app(tmp_path), base_url=BASE) as other:
        other.cookies.set(COOKIE, old_cookie)
        assert other.post(PATH, data=old_form).status_code == 403
        assert counts(repository) == (0, 0, 0, 1, 1)
        other.cookies.clear()
        assert other.post(PATH, data=open_form(other, link)).status_code == 200
    assert counts(repository) == (1, 1, 1, 0, 0)


def test_existing_user_and_registration_forms_cannot_be_swapped(account):
    repository, client = account
    user = User(name="旧用户", email="old@example.com")
    repository.save(user)
    old_message = issue_email_verification(
        repository, user.user_id, BASE + "/web/verify-email"
    )
    _, link = issue(repository)
    new_form = open_form(client, link)
    old_page = client.get(old_message.activation_url)
    old_form = ConfirmationForm(old_page.text).values
    assert client.post(PATH, data=old_form).status_code == 403
    assert client.post("/web/verify-email", data=new_form).status_code == 403
    assert not repository.is_email_verified(user.user_id)
    assert repository.get_by_email("learner@example.com") is None
    assert client.post("/web/verify-email", data=old_form).status_code == 200
    assert client.cookies.get(COOKIE)
    assert client.post(PATH, data=new_form).status_code == 200
    assert not client.cookies
    assert repository.is_email_verified(user.user_id)


def test_old_flow_does_not_consume_registration_link_even_after_reopening(account):
    repository, client = account
    _, link = issue(repository)
    token = parse_qs(urlsplit(link).query)["token"][0]
    old_page = client.get("/web/verify-email?token=" + token)
    assert (
        client.post(
            "/web/verify-email", data=ConfirmationForm(old_page.text).values
        ).status_code
        == 400
    )
    assert counts(repository) == (0, 0, 0, 1, 1)
    assert client.post(PATH, data=open_form(client, link)).status_code == 200


def test_registration_cookie_cannot_be_renamed_to_impersonate_old_flow(account):
    repository, client = account
    _, link = issue(repository)
    form = open_form(client, link)
    cookie = client.cookies.get(COOKIE)
    client.cookies.clear()
    client.cookies.set(pages._COOKIE, cookie)
    assert client.post("/web/verify-email", data=form).status_code == 403
    assert counts(repository) == (0, 0, 0, 1, 1)


def test_registration_form_stays_readonly_and_new_handlers_not_in_public_schema(
    account,
):
    repository, client = account
    response = client.post(
        "/web/auth/register",
        data={"name": "测试者", "email": "preview@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    assert counts(repository) == (0, 0, 0, 0, 0)
    assert PATH not in client.get("/openapi.json").json()["paths"]
    assert (
        client.post(
            "/web/auth/login",
            data={"email": "preview@example.com", "password": PASSWORD},
        ).status_code
        == 503
    )


def test_local_http_confirmation_works_without_secure_cookie(tmp_path):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    _, link = issue(repository)
    token = parse_qs(urlsplit(link).query)["token"][0]
    with TestClient(make_app(tmp_path), base_url="http://127.0.0.1:8777") as client:
        response = client.get(PATH + "?token=" + token)
        assert "Secure" not in response.headers["set-cookie"]
        form = ConfirmationForm(response.text).values
        result = client.post(
            PATH, data=form, headers={"Origin": "http://127.0.0.1:8777"}
        )
        assert result.status_code == 200
    assert counts(repository) == (1, 1, 1, 0, 0)
