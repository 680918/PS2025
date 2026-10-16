import smtplib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from html.parser import HTMLParser
from threading import Event
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from api.account_pages import SESSION_COOKIE
from api import account_pages
from api.registration_pages import RegistrationMailConfig
from security.email_verification import (
    issue_email_verification,
    confirm_email_verification,
)
from security.passwords import hash_password
from security.verification_mailer import SMTPSettings
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


BASE = "https://coach.example.com"
PASSWORD = " a quiet place to grow "


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.values[attrs["name"]] = attrs.get("value", "")


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("no SMTP in account web tests")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    yield
    assert calls == []


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, password_hash):
    repo = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="测试成长者", email="learner@example.com")
    repo.save(user)
    repo.save_initial_password_hash(user.user_id, password_hash)
    message = issue_email_verification(repo, user.user_id, BASE + "/web/verify-email")
    token = parse_qs(urlsplit(message.activation_url).query)["token"][0]
    confirm_email_verification(repo, token)
    app = create_account_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        yield app, repo, client, user


def login(client, **changes):
    fields = dict(
        email="learner@example.com",
        password=PASSWORD,
        csrf=Inputs(client.get("/web/login").text).values["csrf"],
    )
    fields.update(changes)
    return client.post("/web/auth/login", data=fields, follow_redirects=False)


def test_login_private_welcome_logout_and_old_cookie_replay(setup):
    _, repo, client, user = setup
    denied = client.get("/web/welcome", follow_redirects=False)
    assert denied.status_code == 303 and denied.headers["location"] == "/web/login"
    assert login(client).status_code == 303
    token = client.cookies.get(SESSION_COOKIE)
    assert len(token) == 43
    welcome = client.get("/web/welcome")
    assert "欢迎回来，测试成长者。" in welcome.text
    assert "l***@example.com" in welcome.text
    assert "账户已经准备好" not in welcome.text
    assert "准备中" in welcome.text
    for value in (token, user.user_id, user.email, PASSWORD, "$argon2id$"):
        assert value not in welcome.text
    assert welcome.headers["cache-control"] == "no-store"
    assert welcome.headers["referrer-policy"] == "no-referrer"
    assert (
        client.get("/web/login", follow_redirects=False).headers["location"]
        == "/web/welcome"
    )
    fields = Inputs(welcome.text).values
    response = client.post("/web/auth/logout", data=fields, follow_redirects=False)
    assert response.status_code == 303
    assert "Max-Age=0" in response.headers["set-cookie"]
    client.cookies.set(SESSION_COOKIE, token)
    assert (
        client.get("/web/welcome", follow_redirects=False).headers["location"]
        == "/web/login"
    )
    with sqlite3.connect(repo.database_path) as connection:
        assert (
            connection.execute("SELECT revoked_at FROM login_sessions").fetchone()[0]
            is not None
        )


def test_login_cookie_flags_and_no_password_echo(setup):
    _, _, client, _ = setup
    response = login(client)
    cookies = response.headers.get_list("set-cookie")
    session = next(value for value in cookies if value.startswith(SESSION_COOKIE + "="))
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/web", "Max-Age="):
        assert flag in session
    assert PASSWORD not in response.text + str(response.headers)
    assert "token=" not in response.headers["location"]


@pytest.mark.parametrize(
    "kind", ["missing", "wrong", "cross-site", "origin", "expired"]
)
def test_login_rejects_csrf_failures_without_session(setup, monkeypatch, kind):
    _, repo, client, _ = setup
    csrf = Inputs(client.get("/web/login").text).values["csrf"]
    headers = {}
    if kind == "missing":
        client.cookies.clear()
    if kind == "wrong":
        csrf = "x" * 43
    if kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "origin":
        headers["origin"] = "https://attacker.example"
    if kind == "expired":
        old = account_pages.time()
        monkeypatch.setattr(account_pages, "time", lambda: old + 1801)
    response = client.post(
        "/web/auth/login",
        data={"csrf": csrf, "email": "learner@example.com", "password": PASSWORD},
        headers=headers,
    )
    assert response.status_code == 403
    with sqlite3.connect(repo.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM login_sessions").fetchone()[0] == 0
        )


def test_unknown_wrong_password_and_unverified_return_same_message(setup):
    _, repo, client, _ = setup
    first = login(client, email="missing@example.com")
    second = login(client, password="wrong password phrase")
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE user_email_verifications SET verified_at=NULL")
    third = login(client)
    for response in (first, second, third):
        assert response.status_code == 401
        assert "邮箱或密码不正确，或邮箱尚未完成验证。" in response.text
        assert PASSWORD not in response.text


def test_logout_needs_post_csrf_and_same_origin(setup):
    _, _, client, _ = setup
    login(client)
    assert client.get("/web/auth/logout").status_code == 405
    assert client.post("/web/auth/logout", data={"csrf": "bad"}).status_code == 403
    fields = Inputs(client.get("/web/welcome").text).values
    assert (
        client.post(
            "/web/auth/logout",
            data=fields,
            headers={"origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert client.get("/web/welcome").status_code == 200
    assert (
        client.post("/web/auth/logout", data=fields, follow_redirects=False).status_code
        == 303
    )


def test_other_browser_cannot_read_welcome_or_replay_login_challenge(setup):
    app, _, client, _ = setup
    csrf = Inputs(client.get("/web/login").text).values["csrf"]
    with TestClient(app, base_url=BASE) as other:
        assert other.get("/web/welcome", follow_redirects=False).status_code == 303
        assert (
            other.post(
                "/web/auth/login",
                data={
                    "csrf": csrf,
                    "email": "learner@example.com",
                    "password": PASSWORD,
                },
            ).status_code
            == 403
        )


def test_account_app_has_no_legacy_user_id_paths_or_docs(setup):
    _, repo, client, _ = setup
    for path in (
        "/web/journeys/other/continue?user_id=other",
        "/users/register",
        "/docs",
        "/openapi.json",
    ):
        assert client.get(path).status_code == 404
    assert (
        client.post(
            "/web/register", data={"name": "bypass", "email": "bypass@example.com"}
        ).status_code
        == 405
    )
    with sqlite3.connect(repo.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_login_rate_limit_is_not_reset_by_forwarded_headers(setup):
    _, _, client, _ = setup
    csrf = Inputs(client.get("/web/login").text).values["csrf"]
    for i in range(5):
        response = client.post(
            "/web/auth/login",
            data={"csrf": csrf, "email": "missing@example.com", "password": PASSWORD},
            headers={"x-forwarded-for": f"192.0.2.{i}"},
        )
        assert response.status_code == 401
    response = client.post(
        "/web/auth/login",
        data={"csrf": csrf, "email": "learner@example.com", "password": PASSWORD},
    )
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 60


def test_database_failure_never_leaks_details_or_sets_session(setup, monkeypatch):
    _, _, client, _ = setup

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("private database path")

    monkeypatch.setattr(account_pages, "sign_in", broken)
    response = login(client)
    assert response.status_code == 503
    assert "private database path" not in response.text
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")


def test_complete_registration_mail_confirmation_login_logout(tmp_path):
    messages = []
    config = RegistrationMailConfig(
        BASE + "/web/verify-registration",
        SMTPSettings("sender@163.com", "fake-code"),
        simulated=True,
        sender=lambda message, settings, **kwargs: messages.append(message),
    )
    app = create_account_app(tmp_path, registration_mail=config)
    with TestClient(app, base_url=BASE) as client:
        csrf = Inputs(client.get("/web/register").text).values["csrf"]
        saved = client.post(
            "/web/auth/register",
            data={
                "csrf": csrf,
                "name": "新成长者",
                "email": "learner@example.com",
                "password": PASSWORD,
            },
        )
        fields = Inputs(saved.text).values
        assert (
            client.post("/web/register/send-verification", data=fields).status_code
            == 200
        )
        fields = Inputs(client.get(messages[0].activation_url).text).values
        verified = client.post("/web/verify-registration", data=fields)
        assert "现在可以使用注册邮箱和密码登录" in verified.text
        assert login(client).status_code == 303
        welcome = client.get("/web/welcome")
        assert "欢迎回来，新成长者。" in welcome.text
        assert (
            client.post(
                "/web/auth/logout",
                data=Inputs(welcome.text).values,
                follow_redirects=False,
            ).status_code
            == 303
        )


def test_password_checks_have_bounded_concurrency_and_recover(setup, monkeypatch):
    app, _, _, _ = setup
    entered, release = Event(), Event()
    calls = []

    def blocked(*args, **kwargs):
        calls.append(True)
        if len(calls) >= 2:
            entered.set()
        assert release.wait(10)
        return None

    monkeypatch.setattr(account_pages, "sign_in", blocked)
    with ExitStack() as stack:
        clients = [
            stack.enter_context(TestClient(app, base_url=BASE)) for _ in range(3)
        ]
        forms = [
            {
                "csrf": Inputs(client.get("/web/login").text).values["csrf"],
                "email": "learner@example.com",
                "password": PASSWORD,
            }
            for client in clients
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            workers = [
                pool.submit(clients[i].post, "/web/auth/login", data=forms[i])
                for i in range(2)
            ]
            try:
                assert entered.wait(10)
                busy = clients[2].post("/web/auth/login", data=forms[2])
                assert busy.status_code == 503 and busy.headers["retry-after"] == "2"
                assert len(calls) == 2
            finally:
                release.set()
            assert all(
                worker.result(timeout=10).status_code == 401 for worker in workers
            )
        assert clients[2].post("/web/auth/login", data=forms[2]).status_code == 401
        assert len(calls) == 3


def test_private_page_ignores_spoofed_user_id_and_escapes_name(setup):
    _, repo, client, user = setup
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "UPDATE users SET name=? WHERE user_id=?",
            ("<script>bad()</script>", user.user_id),
        )
    login(client)
    page = client.get("/web/welcome?user_id=somebody-else")
    assert page.status_code == 200
    assert "&lt;script&gt;bad()&lt;/script&gt;" in page.text
    assert "<script>" not in page.text


def test_session_survives_app_restart_but_old_logout_csrf_does_not(setup):
    _, repo, client, _ = setup
    login(client)
    token = client.cookies.get(SESSION_COOKIE)
    old_form = Inputs(client.get("/web/welcome").text).values
    restarted = create_account_app(repo.database_path.parent)
    with TestClient(restarted, base_url=BASE) as fresh:
        fresh.cookies.set(SESSION_COOKIE, token)
        page = fresh.get("/web/welcome")
        assert page.status_code == 200
        assert fresh.post("/web/auth/logout", data=old_form).status_code == 403
        assert (
            fresh.post(
                "/web/auth/logout",
                data=Inputs(page.text).values,
                follow_redirects=False,
            ).status_code
            == 303
        )


@pytest.mark.parametrize(
    "body, content_type",
    [
        ("x" * 4097, "application/x-www-form-urlencoded"),
        ("csrf=x&csrf=y&email=x&password=x", "application/x-www-form-urlencoded"),
        ("{}", "application/json"),
        ("csrf=x&email=%FF&password=x", "application/x-www-form-urlencoded"),
    ],
)
def test_invalid_login_bodies_never_reach_password_checker(
    setup, monkeypatch, body, content_type
):
    _, _, client, _ = setup
    client.get("/web/login")
    monkeypatch.setattr(
        account_pages, "sign_in", lambda *a, **k: pytest.fail("must not verify")
    )
    response = client.post(
        "/web/auth/login", content=body, headers={"content-type": content_type}
    )
    assert response.status_code == 400


def test_logout_database_failure_retains_session_for_retry(setup, monkeypatch):
    _, _, client, _ = setup
    login(client)
    fields = Inputs(client.get("/web/welcome").text).values

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("private database details")

    monkeypatch.setattr(account_pages, "sign_out", broken)
    response = client.post("/web/auth/logout", data=fields)
    assert response.status_code == 503
    assert "private database details" not in response.text
    assert "set-cookie" not in response.headers
    assert client.get("/web/welcome").status_code == 200
