import re
import smtplib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from html.parser import HTMLParser
from threading import Event
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api import registration_pages as pages
from security.verification_mailer import (
    SMTPSettings,
    MailDeliveryError,
    MailConfigurationError,
)
from user.sqlite_repository import SQLiteUserRepository


PENDING = "/web/register/pending"
SEND = "/web/register/send-verification"
BASE = "https://coach.example.com"
SETTINGS = SMTPSettings("sender@163.com", "fake-authorization-code")
PASSWORD = " a quiet registration phrase "


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.values[attrs["name"]] = attrs.get("value", "")


def make_app(directory, config=None):
    return create_app(
        directory,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
        registration_mail=config,
    )


@pytest.fixture(autouse=True)
def no_real_smtp(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("no real SMTP in web mail tests")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    yield
    assert calls == []


@pytest.fixture
def setup(tmp_path):
    messages, outcomes = [], [None]

    def sender(message, settings, *, now=None):
        assert settings == SETTINGS
        messages.append(message)
        if outcomes[0] is not None:
            raise outcomes[0]

    config = pages.RegistrationMailConfig(
        BASE + "/web/verify-registration", SETTINGS, simulated=True, sender=sender
    )
    app = make_app(tmp_path, config)
    repository = SQLiteUserRepository(tmp_path / "users.db")
    with TestClient(app, base_url=BASE) as client:
        yield app, repository, client, messages, outcomes, config


def save(client, email="learner@example.com"):
    csrf = Inputs(client.get("/web/register").text).values["csrf"]
    response = client.post(
        "/web/auth/register",
        data={"csrf": csrf, "name": "测试成长者", "email": email, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client.get(PENDING)


def form(client):
    return Inputs(client.get(PENDING).text).values


def post(client, fields=None, **kwargs):
    return client.post(
        SEND,
        data=fields if fields is not None else form(client),
        follow_redirects=False,
        **kwargs,
    )


def rows(repo, table):
    assert table in {
        "users",
        "user_passwords",
        "pending_registrations",
        "registration_mail_deliveries",
        "registration_email_verifications",
    }
    with sqlite3.connect(repo.database_path) as connection:
        return connection.execute(f"SELECT * FROM {table}").fetchall()


def age_attempt(repo):
    # Advance only this disposable test attempt past its cooldown; no real wait.
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "UPDATE registration_email_verifications SET issued_at = issued_at - 61"
        )


def test_first_send_refresh_and_replayed_post_submit_once_without_creating_account(
    setup,
):
    _, repo, client, messages, _, _ = setup
    waiting = save(client)
    assert waiting.status_code == 200
    assert "本机模拟 · 不会发送真实邮件" in waiting.text
    assert "模拟发送验证邮件" in waiting.text
    fields = Inputs(waiting.text).values
    assert fields["action"] == "send"
    assert len(fields["csrf"]) == 75
    assert messages == []
    before = repo.database_path.read_bytes()
    for _ in range(3):
        assert client.get(PENDING).status_code == 200
    assert repo.database_path.read_bytes() == before
    response = post(client, fields)
    assert response.status_code == 303
    assert response.headers["location"] == PENDING
    assert "set-cookie" not in response.headers
    assert len(messages) == 1
    accepted = client.get(PENDING)
    assert "验证邮件已模拟提交" in accepted.text
    assert "已完成模拟提交" in accepted.text
    assert "<form" not in accepted.text
    assert "刷新申请进度" in accepted.text
    assert "邮箱验证成功" not in accepted.text
    assert rows(repo, "users") == rows(repo, "user_passwords") == []
    original_link = rows(repo, "registration_email_verifications")
    assert post(client, fields).status_code == 303
    assert rows(repo, "registration_email_verifications") == original_link
    assert len(messages) == 1
    for _ in range(3):
        client.get(PENDING)
    assert len(messages) == 1


def test_confirm_simulated_link_through_protected_web_page_creates_account_once(setup):
    _, repo, client, messages, _, _ = setup
    save(client)
    assert post(client).status_code == 303
    confirmation = client.get(messages[0].activation_url)
    assert "确认邮箱并创建账户" in confirmation.text
    assert rows(repo, "users") == []
    fields = Inputs(confirmation.text).values
    response = client.post("/web/verify-registration", data=fields)
    assert response.status_code == 200
    assert "账户已创建，邮箱已验证" in response.text
    assert len(rows(repo, "users")) == 1
    assert len(rows(repo, "user_passwords")) == 1
    assert rows(repo, "pending_registrations") == []
    assert rows(repo, "registration_mail_deliveries") == []
    assert client.get(PENDING).status_code == 403
    assert (
        client.post(
            "/web/auth/login",
            data={"email": "learner@example.com", "password": PASSWORD},
        ).status_code
        == 503
    )


@pytest.mark.parametrize(
    "code", ["authentication_failed", "recipient_refused", "rejected", "unsupported"]
)
def test_definite_failure_shows_cooldown_then_explicit_retry(setup, code):
    _, repo, client, messages, outcomes, _ = setup
    save(client)
    first_form = form(client)
    outcomes[0] = MailDeliveryError(code, "private raw SMTP response")
    assert post(client, first_form).status_code == 303
    failed = client.get(PENDING)
    assert "邮件暂未发出，可以稍后重试" in failed.text
    assert re.search(r"请在 [1-6]?[0-9] 秒后刷新", failed.text)
    assert "等待后可重试" in failed.text
    assert "<form" not in failed.text
    assert "private raw SMTP response" not in failed.text
    # Replaying the original send is not consent for a retry.
    assert post(client, first_form).status_code == 303
    assert len(messages) == 1
    age_attempt(repo)
    retry_form = form(client)
    assert retry_form["action"] == "retry"
    assert retry_form["csrf"] != first_form["csrf"]
    outcomes[0] = None
    assert post(client, retry_form).status_code == 303
    assert len(messages) == 2
    assert rows(repo, "registration_mail_deliveries")[0][2] == "accepted"
    assert "验证邮件已模拟提交" in client.get(PENDING).text


@pytest.mark.parametrize("code", ["timeout", "connection_failed", "tls_failed"])
def test_uncertain_status_preserves_link_and_has_no_retry_form(setup, code):
    _, repo, client, messages, outcomes, _ = setup
    save(client)
    original_form = form(client)
    outcomes[0] = MailDeliveryError(code, "private raw SMTP response")
    assert post(client, original_form).status_code == 303
    original_link = rows(repo, "registration_email_verifications")
    page = client.get(PENDING)
    assert "发送结果暂未确认" in page.text
    assert "<form" not in page.text
    assert "private raw SMTP response" not in page.text
    age_attempt(repo)
    assert post(client, original_form).status_code == 303
    assert len(messages) == 1
    assert rows(repo, "registration_email_verifications")[0][1] == original_link[0][1]


@pytest.mark.parametrize(
    "kind",
    ["missing", "wrong", "other-browser", "expired", "cross-site", "origin", "action"],
)
def test_invalid_mail_form_never_sends_or_prepares_link(setup, monkeypatch, kind):
    app, repo, client, messages, _, _ = setup
    save(client)
    fields = form(client)
    headers = {}
    if kind == "missing":
        fields["csrf"] = ""
    elif kind == "wrong":
        fields["csrf"] = fields["csrf"][:-1] + (
            "0" if fields["csrf"][-1] != "0" else "1"
        )
    elif kind == "expired":
        now = pages.time()
        monkeypatch.setattr(pages, "time", lambda: now + 601)
    elif kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    elif kind == "origin":
        headers["origin"] = "https://attacker.example"
    elif kind == "action":
        fields["action"] = "retry"
    elif kind == "other-browser":
        with TestClient(app, base_url=BASE) as outsider:
            assert post(outsider, fields).status_code == 403
        assert messages == []
        return
    assert post(client, fields, headers=headers).status_code == 403
    assert messages == []
    assert rows(repo, "registration_email_verifications") == []
    assert rows(repo, "registration_mail_deliveries") == []


@pytest.mark.parametrize(
    "payload,content_type",
    [
        ("csrf=x&csrf=y&action=send", "application/x-www-form-urlencoded"),
        (
            "csrf=x&action=send&email=attacker%40example.com",
            "application/x-www-form-urlencoded",
        ),
        ("csrf=%FF&action=send", "application/x-www-form-urlencoded"),
        ("x" * 2049, "application/x-www-form-urlencoded"),
        ("{}", "application/json"),
        ("csrf=x&action=delete", "application/x-www-form-urlencoded"),
    ],
)
def test_malformed_or_oversize_submission_is_rejected_before_delivery(
    setup, payload, content_type
):
    _, repo, client, messages, _, _ = setup
    save(client)
    response = client.post(
        SEND, content=payload, headers={"content-type": content_type}
    )
    assert response.status_code == 400
    assert messages == []
    assert rows(repo, "registration_mail_deliveries") == []


def test_form_from_other_application_cannot_be_replayed(setup):
    app, repo, client, messages, _, _ = setup
    save(client)
    fields = form(client)
    with TestClient(app, base_url=BASE) as other:
        save(other, "other@example.com")
        assert post(other, fields).status_code == 403
    assert messages == []
    assert len(rows(repo, "pending_registrations")) == 2


def test_expired_application_cannot_send_or_keep_operable_form(setup):
    _, repo, client, messages, _, _ = setup
    save(client)
    fields = form(client)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "UPDATE pending_registrations SET created_at=created_at-7200, expires_at=expires_at-7200"
        )
    assert post(client, fields).status_code == 403
    assert client.get(PENDING).status_code == 403
    assert messages == []


def test_parallel_replayed_form_sends_once_and_get_shows_in_flight_state(setup):
    app, repo, client, messages, outcomes, config = setup
    entered, release = Event(), Event()

    def blocked(message, settings, *, now=None):
        messages.append(message)
        entered.set()
        assert release.wait(10)

    # Build the app with the blocking simulator before issuing its CSRF token.
    app = make_app(
        repo.database_path.parent,
        pages.RegistrationMailConfig(
            config.activation_url, SETTINGS, simulated=True, sender=blocked
        ),
    )
    with TestClient(app, base_url=BASE) as local:
        save(local)
        fields = form(local)
        with ThreadPoolExecutor(max_workers=2) as pool:
            worker = pool.submit(post, local, fields)
            try:
                assert entered.wait(10)
                page = local.get(PENDING)
                assert "正在确认邮件发送结果" in page.text
                assert "<form" not in page.text
                assert post(local, fields).status_code == 303
                assert len(messages) == 1
            finally:
                release.set()
            assert worker.result(timeout=10).status_code == 303
        assert "验证邮件已模拟提交" in local.get(PENDING).text


def test_mail_rate_limit_is_separate_and_not_reset_by_forwarded_headers_or_form_refresh(
    setup,
):
    _, repo, client, messages, _, _ = setup
    save(client)
    fields = form(client)
    for i in range(3):
        assert (
            post(
                client, fields, headers={"x-forwarded-for": f"192.0.2.{i}"}
            ).status_code
            == 303
        )
    response = post(client, fields, headers={"x-forwarded-for": "192.0.2.100"})
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 60
    assert "邮件操作有些频繁" in response.text
    assert len(messages) == 1
    assert client.get(PENDING).status_code == 200
    assert client.get("/web/register").status_code == 200


def test_private_fields_and_server_error_never_appear_in_result_or_headers(setup):
    _, repo, client, messages, outcomes, config = setup
    save(client)
    owner_cookie = client.cookies.get(pages._APPLICATION_COOKIE)
    fields = form(client)
    outcomes[0] = RuntimeError("private secret server response")
    response = post(client, fields)
    page = client.get(PENDING)
    token = parse_qs(urlsplit(messages[0].activation_url).query)["token"][0]
    for value in [
        owner_cookie,
        *owner_cookie.split("."),
        PASSWORD,
        SETTINGS.authorization_code,
        "learner@example.com",
        messages[0].activation_url,
        token,
        "private secret server response",
        "$argon2id$",
    ]:
        assert value not in response.text + page.text + str(response.headers) + repr(
            config
        )
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["referrer-policy"] == "no-referrer"
    assert "form-action 'self'" in page.headers["content-security-policy"]
    assert "set-cookie" not in page.headers


def test_disabled_default_does_not_read_smtp_env_or_offer_send_control(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SMTP_ENABLED", "true")
    app = make_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        page = save(client)
        assert "<form" not in page.text
        assert "无需等待邮件" in page.text
        assert client.get(SEND).status_code == 405
        assert post(client, {"csrf": "x", "action": "send"}).status_code == 403
    repo = SQLiteUserRepository(tmp_path / "users.db")
    assert rows(repo, "registration_mail_deliveries") == []


def test_database_failure_is_generic_and_does_not_promise_no_mail_was_sent(
    setup, monkeypatch
):
    _, repo, client, messages, _, _ = setup
    save(client)
    fields = form(client)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("private database path")

    monkeypatch.setattr(pages, "send_registration_verification", fail)
    response = post(client, fields)
    assert response.status_code == 503
    assert "暂时无法处理邮件操作" in response.text
    assert "private database path" not in response.text
    assert "没有发送邮件" not in response.text
    assert messages == []


def test_config_rejects_unsafe_or_ambiguous_modes():
    with pytest.raises(ValueError):
        pages.RegistrationMailConfig("http://untrusted.example/verify", SETTINGS)
    with pytest.raises(MailConfigurationError):
        pages.RegistrationMailConfig(BASE + "/verify", SETTINGS, simulated=True)
    with pytest.raises(MailConfigurationError):
        pages.RegistrationMailConfig(
            BASE + "/verify", SETTINGS, sender=lambda *a, **k: None
        )
    assert "fake-authorization-code" not in repr(
        pages.RegistrationMailConfig(BASE + "/verify", SETTINGS)
    )


def test_restarted_app_keeps_application_but_requires_fresh_operation_form(setup):
    _, repo, client, messages, _, config = setup
    save(client)
    original = form(client)
    owner = client.cookies.get(pages._APPLICATION_COOKIE)
    restarted = make_app(repo.database_path.parent, config)
    with TestClient(restarted, base_url=BASE) as reopened:
        reopened.cookies.set(pages._APPLICATION_COOKIE, owner)
        fresh = form(reopened)
        assert fresh["csrf"] != original["csrf"]
        assert post(reopened, original).status_code == 403
        assert messages == []
        assert post(reopened, fresh).status_code == 303
    assert len(messages) == 1


def test_expired_operation_can_be_refreshed_without_reentering_password(
    setup, monkeypatch
):
    _, repo, client, messages, _, _ = setup
    save(client)
    original = form(client)
    previous_time = pages.time()
    monkeypatch.setattr(pages, "time", lambda: previous_time + 601)
    assert post(client, original).status_code == 403
    fresh = form(client)
    assert fresh["csrf"] != original["csrf"]
    assert post(client, fresh).status_code == 303
    assert len(messages) == 1
    assert len(rows(repo, "pending_registrations")) == 1


def test_configured_url_does_not_follow_spoofed_host_or_forwarded_headers(setup):
    _, _, client, messages, _, _ = setup
    save(client)
    fields = form(client)
    assert (
        post(
            client,
            fields,
            headers={"host": "attacker.example", "x-forwarded-host": "evil.example"},
        ).status_code
        == 303
    )
    assert messages[0].activation_url.startswith(
        BASE + "/web/verify-registration?token="
    )
    assert messages[0].recipient == "learner@example.com"


def test_result_write_failure_displays_pending_result_and_blocks_duplicate(
    setup, monkeypatch
):
    _, repo, client, messages, _, _ = setup
    save(client)
    original = form(client)

    def cannot_finish(*args, **kwargs):
        raise sqlite3.OperationalError("private database path")

    monkeypatch.setattr(
        SQLiteUserRepository, "finish_registration_delivery", cannot_finish
    )
    assert post(client, original).status_code == 303
    page = client.get(PENDING)
    assert "正在确认邮件发送结果" in page.text
    assert "<form" not in page.text
    assert post(client, original).status_code == 303
    assert len(messages) == 1
    assert rows(repo, "registration_mail_deliveries")[0][2] == "sending"


def test_network_capacity_is_bounded_and_frees_slots_after_completion(setup):
    _, repo, _, messages, _, config = setup
    ready, release = Event(), Event()

    def blocked(message, settings, *, now=None):
        messages.append(message)
        if len(messages) >= 2:
            ready.set()
        assert release.wait(10)

    app = make_app(
        repo.database_path.parent,
        pages.RegistrationMailConfig(
            config.activation_url, SETTINGS, simulated=True, sender=blocked
        ),
    )
    with ExitStack() as stack:
        clients = [
            stack.enter_context(
                TestClient(app, base_url=BASE, client=(f"192.0.2.{i + 1}", 2000 + i))
            )
            for i in range(3)
        ]
        forms = [
            Inputs(save(client, f"learner{i}@example.com").text).values
            for i, client in enumerate(clients)
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            workers = [pool.submit(post, clients[i], forms[i]) for i in range(2)]
            try:
                assert ready.wait(10)
                busy = post(clients[2], forms[2])
                assert busy.status_code == 503
                assert busy.headers["retry-after"] == "2"
                assert len(messages) == 2
                assert len(rows(repo, "registration_mail_deliveries")) == 2
            finally:
                release.set()
            assert all(
                worker.result(timeout=10).status_code == 303 for worker in workers
            )
        assert post(clients[2], forms[2]).status_code == 303
        assert len(messages) == 3
        assert all(
            row[2] == "accepted" for row in rows(repo, "registration_mail_deliveries")
        )


def test_total_mail_quota_applies_across_transport_peers(setup):
    app, _, client, messages, _, _ = setup
    save(client)
    fields = form(client)
    cookie = client.cookies.get(pages._APPLICATION_COOKIE)
    for i in range(31):
        with TestClient(
            app, base_url=BASE, client=(f"192.0.2.{i + 1}", 2000 + i)
        ) as peer:
            peer.cookies.set(pages._APPLICATION_COOKIE, cookie)
            response = post(peer, fields)
            assert response.status_code == (303 if i < 30 else 429)
    assert len(messages) == 1
