import hashlib
import smtplib
import sqlite3
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from api.registration_pages import RegistrationMailConfig
from api import password_reset_pages as pages
from security.email_verification import (
    issue_email_verification,
    confirm_email_verification,
)
from security.password_reset import (
    issue_password_reset,
    PasswordResetMessage,
    PasswordChangedMessage,
)
from security.passwords import hash_password
from security.verification_mailer import SMTPSettings
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


BASE = "https://coach.example.com"
OLD = "a quiet place to grow today"
NEW = "每天读书，并且实践新的知识2026"


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.fields = {}
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.fields[attrs["name"]] = attrs.get("value", "")
        if tag == "a":
            self.links.append(attrs.get("href", ""))


@pytest.fixture(autouse=True)
def no_paid_services(monkeypatch):
    import requests

    def forbidden(*args, **kwargs):
        pytest.fail("no real SMTP or AI")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(OLD)


@pytest.fixture
def setup(tmp_path, password_hash):
    repo = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="虚构成长者", email="reader@example.com")
    repo.save(user)
    repo.save_initial_password_hash(user.user_id, password_hash)
    verification = issue_email_verification(repo, user.user_id, BASE + "/verify")
    confirm_email_verification(
        repo, parse_qs(urlsplit(verification.activation_url).query)["token"][0]
    )
    sent = []
    config = RegistrationMailConfig(
        BASE + "/web/verify-registration",
        SMTPSettings("sender@163.com", "fake-code"),
        simulated=True,
        sender=lambda msg, settings: sent.append(msg),
    )
    app = create_account_app(tmp_path, registration_mail=config)
    with TestClient(app, base_url=BASE) as client:
        yield app, repo, client, user, sent, config


def request_reset(client, email="reader@example.com", **changes):
    values = Inputs(client.get("/web/forgot-password").text).fields
    values["email"] = email
    values.update(changes)
    return client.post("/web/forgot-password", data=values, follow_redirects=False)


def submit_reset(client, password=NEW, confirmation=NEW, **changes):
    values = Inputs(client.get("/web/reset-password").text).fields
    values.update(password=password, confirmation=confirmation, **changes)
    return client.post("/web/reset-password", data=values, follow_redirects=False)


def login(client, password):
    values = Inputs(client.get("/web/login").text).fields
    values.update(email="reader@example.com", password=password)
    return client.post("/web/auth/login", data=values, follow_redirects=False)


def test_complete_recovery_clean_url_no_token_in_form_and_old_sessions_revoked(setup):
    app, repo, client, user, sent, _ = setup
    from coach.materials import MaterialRepository
    from conversation.coach_repository import CoachRepository

    material = MaterialRepository(repo.database_path.parent / "coach_library.db")
    material_id = material.add(
        user.user_id, "保留资料.txt", "保留的知识点".encode("utf-8")
    )
    material.select(user.user_id, material_id)
    dialogue = CoachRepository(repo.database_path.parent / "coach_conversations.db")
    now = int(datetime.now(timezone.utc).timestamp())
    nonce = "a" * 43
    assert dialogue.claim(user.user_id, nonce, "帮我整理知识点", now=now) == "claimed"
    dialogue.finish(
        user.user_id,
        nonce,
        "已整理",
        {"topic": "主题学习", "progress": "已讨论知识点", "next_step": "继续实践"},
        now=now,
        draft={"title": "保留教案", "topic": "主题学习", "content": "需要保留的教案"},
    )
    lesson = dialogue.list_knowledge(user.user_id, status="pending")[0]
    assert dialogue.confirm_knowledge(user.user_id, lesson["knowledge_id"])
    before_assets = {
        name: hashlib.sha256(
            (repo.database_path.parent / name).read_bytes()
        ).hexdigest()
        for name in ("coach_library.db", "coach_conversations.db")
    }
    assert login(client, OLD).status_code == 303
    old_cookie = client.cookies.get("coach_login_session")
    assert request_reset(client).status_code == 303
    assert len(sent) == 1 and isinstance(sent[0], PasswordResetMessage)
    raw = parse_qs(urlsplit(sent[0].activation_url).query)["token"][0]
    assert client.get("/web/welcome").status_code == 200
    with TestClient(app, base_url=BASE) as other_browser:
        start = other_browser.get(sent[0].activation_url, follow_redirects=False)
        assert (
            start.status_code == 303
            and start.headers["location"] == "/web/reset-password"
        )
        assert all(
            flag in start.headers["set-cookie"]
            for flag in ("Secure", "HttpOnly", "SameSite=lax", "Path=/web")
        )
        form = other_browser.get(start.headers["location"])
        assert (
            raw not in form.text
            and user.email not in form.text
            and user.user_id not in form.text
        )
        result = submit_reset(other_browser)
        assert (
            result.status_code == 303
            and result.headers["location"] == "/web/password-reset-complete"
        )
        assert len(sent) == 2 and isinstance(sent[1], PasswordChangedMessage)
        assert login(other_browser, OLD).status_code == 401
        assert login(other_browser, NEW).status_code == 303
        assert other_browser.get(sent[0].activation_url).status_code == 400
    client.cookies.set("coach_login_session", old_cookie)
    assert (
        client.get("/web/welcome", follow_redirects=False).headers["location"]
        == "/web/login"
    )
    assert repo.get_by_id(user.user_id).name == user.name
    for name, before_hash in before_assets.items():
        assert (
            hashlib.sha256((repo.database_path.parent / name).read_bytes()).hexdigest()
            == before_hash
        )


def test_email_landing_uses_lax_only_for_reset_context_not_login_or_request(setup):
    _, _, client, _, sent, _ = setup
    initial = client.get("/web/forgot-password")
    assert "SameSite=strict" in initial.headers["set-cookie"]
    assert request_reset(client).status_code == 303
    landing = client.get(
        sent[0].activation_url,
        headers={"sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate"},
        follow_redirects=False,
    )
    assert landing.status_code == 303
    cookie = landing.headers["set-cookie"]
    assert cookie.startswith(pages.RESET_COOKIE + "=")
    for flag in ("SameSite=lax", "HttpOnly", "Secure", "Max-Age=1800", "Path=/web"):
        assert flag in cookie
    assert "coach_login_session" not in cookie
    assert landing.headers["location"] == "/web/reset-password"
    form = client.get(landing.headers["location"])
    assert "无需再次填写邮箱" in form.text
    fields = Inputs(form.text).fields
    assert set(fields) == {"csrf", "password", "confirmation"}


@pytest.mark.parametrize(
    "headers",
    [
        {"sec-fetch-site": "cross-site"},
        {"origin": "https://mail-other.example"},
        {"origin": "null"},
    ],
)
def test_lax_reset_context_still_cannot_authorize_cross_site_password_change(
    setup, headers
):
    _, repo, client, user, sent, _ = setup
    request_reset(client)
    client.get(sent[0].activation_url)
    fields = Inputs(client.get("/web/reset-password").text).fields
    fields.update(password=NEW, confirmation=NEW)
    before = repo.get_password_hash(user.user_id)
    response = client.post("/web/reset-password", data=fields, headers=headers)
    assert response.status_code == 403
    assert repo.get_password_hash(user.user_id) == before
    assert submit_reset(client).status_code == 303


def test_unknown_unverified_and_failed_delivery_have_same_generic_response(
    setup, monkeypatch
):
    _, repo, client, user, sent, _ = setup
    known = request_reset(client)
    unknown = request_reset(client, "missing@example.com")
    assert known.status_code == unknown.status_code == 303
    assert known.headers["location"] == unknown.headers["location"]
    receipt = client.get(known.headers["location"])
    assert "若邮箱已注册并完成验证" in receipt.text and "投递成功" in receipt.text
    assert "未能投递" in receipt.text and user.email not in receipt.text
    assert len(sent) == 1
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE user_email_verifications SET verified_at=NULL")
    # Clear address cooldown by advancing the limiter's clock in a separate fresh app.
    app = create_account_app(repo.database_path.parent, registration_mail=setup[5])
    with TestClient(app, base_url=BASE) as fresh:
        result = request_reset(fresh)
        assert (
            result.status_code == 303
            and result.headers["location"] == known.headers["location"]
        )
    assert len(sent) == 1


@pytest.mark.parametrize(
    "kind",
    ["missing", "csrf", "unicode", "origin", "null-origin", "cross-site", "expired"],
)
def test_recovery_rejects_invalid_browser_context(setup, monkeypatch, kind):
    _, _, client, _, sent, _ = setup
    values = Inputs(client.get("/web/forgot-password").text).fields
    values["email"] = "reader@example.com"
    headers = {}
    if kind == "missing":
        client.cookies.clear()
    if kind == "csrf":
        values["csrf"] = "x" * 43
    if kind == "unicode":
        values["csrf"] = "中" * 43
    if kind == "origin":
        headers["origin"] = "https://bad.example"
    if kind == "null-origin":
        headers["origin"] = "null"
    if kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "expired":
        now = pages.time()
        monkeypatch.setattr(pages, "time", lambda: now + 1801)
    assert (
        client.post("/web/forgot-password", data=values, headers=headers).status_code
        == 403
    )
    assert sent == []


@pytest.mark.parametrize(
    "payload,ctype",
    [
        ("x" * 4097, "application/x-www-form-urlencoded"),
        ("{}", "application/json"),
        ("email=%FF&csrf=x", "application/x-www-form-urlencoded"),
        ("email=x&email=y&csrf=x", "application/x-www-form-urlencoded"),
    ],
)
def test_bad_request_bodies_do_not_send(setup, payload, ctype):
    _, _, client, _, sent, _ = setup
    client.get("/web/forgot-password")
    assert (
        client.post(
            "/web/forgot-password", content=payload, headers={"content-type": ctype}
        ).status_code
        == 400
    )
    assert sent == []


def test_same_email_cooldown_unknown_email_and_rate_limits_ignore_forwarded_headers(
    setup,
):
    _, _, client, _, sent, _ = setup
    assert request_reset(client).status_code == 303
    repeated = request_reset(client)
    assert repeated.status_code == 429 and "Retry-After" in repeated.headers
    assert request_reset(client, "missing@example.com").status_code == 303
    denied = client.post(
        "/web/forgot-password", data={}, headers={"x-forwarded-for": "different-peer"}
    )
    assert denied.status_code == 429 and len(sent) == 1


def test_password_mismatch_short_input_csrf_and_expired_link_do_not_change_account(
    setup,
):
    _, repo, client, user, sent, _ = setup
    assert request_reset(client).status_code == 303
    client.get(sent[0].activation_url)
    before = repo.get_password_hash(user.user_id)
    for changes in (
        {"password": "short", "confirmation": "short"},
        {"confirmation": OLD},
        {"csrf": "中" * 43},
    ):
        response = submit_reset(client, **changes)
        assert (
            response.status_code in (400, 403)
            and NEW not in response.text
            and OLD not in response.text
        )
    assert repo.get_password_hash(user.user_id) == before
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "UPDATE password_reset_tokens SET expires_at=issued_at-1,issued_at=issued_at-1801"
        )
    assert submit_reset(client).status_code == 400
    assert repo.get_password_hash(user.user_id) == before


def test_reset_form_and_post_are_browser_bound_and_cross_origin_rejected(setup):
    app, _, client, _, sent, _ = setup
    request_reset(client)
    client.get(sent[0].activation_url)
    fields = Inputs(client.get("/web/reset-password").text).fields
    fields.update(password=NEW, confirmation=NEW)
    with TestClient(app, base_url=BASE) as stranger:
        assert stranger.post("/web/reset-password", data=fields).status_code == 403
    assert (
        client.post(
            "/web/reset-password",
            data=fields,
            headers={"origin": "https://bad.example"},
        ).status_code
        == 403
    )
    assert client.get("/web/reset-password?token=x&token=y").status_code == 400


def test_no_mail_config_has_actionable_error_and_can_finish_existing_valid_link(setup):
    _, repo, _, user, _, _ = setup
    app = create_account_app(repo.database_path.parent)
    message = issue_password_reset(repo, user.email, BASE + "/web/reset-password")
    with TestClient(app, base_url=BASE) as client:
        response = request_reset(client)
        assert response.status_code == 503 and "邮件发送尚未启用" in response.text
        client.get(message.activation_url)
        assert submit_reset(client).status_code == 303
        assert client.get("/web/trial-reset-mailbox").status_code == 404


def test_simulated_mailbox_is_browser_bound_and_real_mode_does_not_expose_links(setup):
    app, _, client, _, sent, _ = setup
    request_reset(client)
    assert "?token=" in client.get("/web/trial-reset-mailbox").text
    with TestClient(app, base_url=BASE) as stranger:
        assert "?token=" not in stranger.get("/web/trial-reset-mailbox").text
    assert (
        client.get("/web/forgot-password/submitted").headers["referrer-policy"]
        == "no-referrer"
    )
    assert client.get("/web/reset-password").headers["cache-control"] == "no-store"


def test_background_failure_is_redacted_releases_slots_keeps_token_for_uncertain_delivery(
    setup,
):
    _, repo, _, user, _, config = setup

    def broken(*args, **kwargs):
        raise RuntimeError("private provider credentials")

    config = RegistrationMailConfig(
        config.activation_url, config.settings, simulated=True, sender=broken
    )
    app = create_account_app(repo.database_path.parent, registration_mail=config)
    with TestClient(app, base_url=BASE) as client:
        response = request_reset(client)
        assert response.status_code == 303 and "private" not in response.text
        assert request_reset(client, "other@example.com").status_code == 303
    with sqlite3.connect(repo.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[
                0
            ]
            == 1
        )


def test_json_progress_contract_and_stale_login_copy_removed(setup):
    _, _, client, _, sent, _ = setup
    fields = Inputs(client.get("/web/forgot-password").text).fields
    fields["email"] = "reader@example.com"
    response = client.post(
        "/web/forgot-password", data=fields, headers={"accept": "application/json"}
    )
    assert response.json() == {"redirect": "/web/forgot-password/submitted"}
    client.get(sent[0].activation_url)
    fields = Inputs(client.get("/web/reset-password").text).fields
    fields.update(password=NEW, confirmation=OLD)
    error = client.post(
        "/web/reset-password", data=fields, headers={"accept": "application/json"}
    )
    assert error.status_code == 400 and "不一致" in error.json()["error"]
    page = client.get("/web/login")
    assert (
        "/web/forgot-password" in page.text
        and "聊天、学习与知识库将逐步接入" not in page.text
    )
    assert client.get("/static/password-recovery.js").status_code == 200


def test_real_mode_restricts_recipient_and_uses_configured_not_host_header_origin(
    setup, monkeypatch
):
    _, repo, _, user, _, config = setup
    sent = []
    monkeypatch.setattr(
        pages, "send_password_reset_email", lambda msg, settings: sent.append(msg)
    )
    settings = SMTPSettings("self@163.com", "fake-code")
    real = RegistrationMailConfig(
        "https://trusted.example/web/verify-registration",
        settings,
        allowed_recipient=settings.username,
    )
    app = create_account_app(repo.database_path.parent, registration_mail=real)
    with TestClient(app, base_url="https://host-attacker.example") as client:
        assert request_reset(client).status_code == 303
        assert client.get("/web/trial-reset-mailbox").status_code == 404
    assert sent == []
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE users SET email=?", (settings.username,))
        connection.execute(
            "UPDATE user_email_verifications SET email=?", (settings.username,)
        )
    with TestClient(app, base_url="https://host-attacker.example") as client:
        assert request_reset(client, settings.username).status_code == 303
    assert len(sent) == 1 and sent[0].activation_url.startswith(
        "https://trusted.example/web/reset-password?"
    )
