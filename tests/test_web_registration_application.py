import re
import smtplib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from api import registration_pages as pages
from api.app import create_app
from security.email_verification import issue_registration_verification
from security.passwords import verify_password
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


PASSWORD = " a quiet registration phrase "
PATH = "/web/register/pending"


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.values[attrs["name"]] = attrs.get("value", "")


def make_app(directory):
    return create_app(
        directory,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )


@pytest.fixture
def setup(tmp_path, monkeypatch):
    def no_mail(*args, **kwargs):
        raise AssertionError("saving registration must not contact SMTP")

    monkeypatch.setattr(smtplib, "SMTP", no_mail)
    monkeypatch.setattr(smtplib, "SMTP_SSL", no_mail)
    app = make_app(tmp_path)
    repository = SQLiteUserRepository(tmp_path / "users.db")
    with TestClient(app, base_url="https://coach.example.com") as client:
        yield app, repository, client, tmp_path


def csrf(client):
    return Inputs(client.get("/web/register").text).values["csrf"]


def submit(client, **changes):
    fields = {
        "csrf": csrf(client),
        "name": "测试成长者",
        "email": "learner@example.com",
        "password": PASSWORD,
    }
    fields.update(changes)
    return client.post("/web/auth/register", data=fields, follow_redirects=False)


def count(repository, table):
    assert table in {
        "users",
        "user_passwords",
        "user_email_verifications",
        "pending_registrations",
        "registration_browser_bindings",
        "registration_email_verifications",
    }
    with repository._connect() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_save_redirect_cookie_waiting_and_refresh_create_only_one_bound_application(
    setup,
):
    _, repo, client, _ = setup
    response = submit(client, email="  Learner@Example.COM ")
    assert response.status_code == 303
    assert response.headers["location"] == PATH
    assert "token=" not in response.headers["location"]
    cookie = response.headers["set-cookie"]
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/web", "Max-Age="):
        assert flag in cookie
    value = client.cookies.get(pages._APPLICATION_COOKIE)
    request_id, secret = value.split(".")
    assert len(value) == 89
    assert 3500 <= int(re.search(r"Max-Age=(\d+)", cookie).group(1)) <= 3600
    for _ in range(3):
        waiting = client.get(PATH)
        assert waiting.status_code == 200
        assert "申请已保存，等待验证邮箱" in waiting.text
        assert "l***@example.com" in waiting.text
        assert "无需等待邮件" in waiting.text
        assert "北京时间" in waiting.text
        assert "没有保存" not in waiting.text
        assert "set-cookie" not in waiting.headers
        assert waiting.headers["cache-control"] == "no-store"
        assert waiting.headers["referrer-policy"] == "no-referrer"
        assert "<form" not in waiting.text
        for private in (
            value,
            secret,
            request_id,
            PASSWORD,
            "learner@example.com",
            "$argon2id$",
        ):
            assert private not in waiting.text
    assert (
        count(repo, "pending_registrations")
        == count(repo, "registration_browser_bindings")
        == 1
    )
    for table in (
        "users",
        "user_passwords",
        "user_email_verifications",
        "registration_email_verifications",
    ):
        assert count(repo, table) == 0
    with repo._connect() as connection:
        password_hash = connection.execute(
            "SELECT password_hash FROM pending_registrations"
        ).fetchone()[0]
    assert verify_password(PASSWORD, password_hash)
    assert not verify_password(PASSWORD.strip(), password_hash)
    assert PASSWORD.encode() not in repo.database_path.read_bytes()
    assert secret.encode() not in repo.database_path.read_bytes()


def test_repeat_from_owner_does_not_rehash_replace_fields_or_extend_expiry(
    setup, monkeypatch
):
    _, repo, client, _ = setup
    assert submit(client).status_code == 303
    cookie = client.cookies.get(pages._APPLICATION_COOKIE)
    before = repo.database_path.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("valid owned application must be reused")

    monkeypatch.setattr(pages, "begin_browser_registration", forbidden)
    response = submit(
        client, email="different@example.com", password="a different submitted phrase"
    )
    assert response.status_code == 303
    assert "set-cookie" not in response.headers
    assert client.cookies.get(pages._APPLICATION_COOKIE) == cookie
    assert repo.database_path.read_bytes() == before
    assert "l***@example.com" in client.get(PATH).text


@pytest.mark.parametrize(
    "kind",
    ["missing", "malformed", "wrong-secret", "wrong-id", "expired", "other-browser"],
)
def test_waiting_page_needs_owned_active_application_and_never_discloses_it(
    setup, kind
):
    app, repo, client, _ = setup
    assert submit(client).status_code == 303
    original = client.cookies.get(pages._APPLICATION_COOKIE)
    request_id, secret = original.split(".")
    if kind == "missing":
        client.cookies.clear()
    elif kind in {"malformed", "wrong-secret", "wrong-id"}:
        client.cookies.clear()
        changed = (
            "invalid"
            if kind == "malformed"
            else request_id + "." + "a" * 43
            if kind == "wrong-secret"
            else "registration_" + "a" * 32 + "." + secret
        )
        client.cookies.set(pages._APPLICATION_COOKIE, changed)
    elif kind == "expired":
        with repo._connect() as connection:
            connection.execute(
                "UPDATE pending_registrations SET created_at = created_at - 7200, expires_at = expires_at - 7200"
            )
    elif kind == "other-browser":
        with TestClient(app, base_url="https://coach.example.com") as other:
            assert other.get(PATH + "?request_id=" + request_id).status_code == 403
        assert client.get(PATH).status_code == 200
        return
    response = client.get(PATH)
    assert response.status_code == 403
    assert "暂时无法查看这份申请" in response.text
    for private in (secret, request_id, "learner@example.com", PASSWORD):
        assert private not in response.text
    if kind == "expired":
        assert (
            count(repo, "pending_registrations")
            == count(repo, "registration_browser_bindings")
            == 0
        )


def test_request_cookie_survives_restart_while_form_cookie_must_refresh(setup):
    _, _, client, directory = setup
    submit(client)
    cookie = client.cookies.get(pages._APPLICATION_COOKIE)
    restarted = make_app(directory)
    with TestClient(restarted, base_url="https://coach.example.com") as other:
        other.cookies.set(pages._APPLICATION_COOKIE, cookie)
        assert other.get(PATH).status_code == 200
        assert submit(other).status_code == 303


def test_unowned_duplicate_and_existing_account_have_same_private_failure(setup):
    app, repo, client, _ = setup
    submit(client)
    repo.save(User(name="旧用户", email="old@example.com"))
    with TestClient(app, base_url="https://coach.example.com") as other:
        duplicate = submit(other)
        existing = submit(other, email="old@example.com")
        assert duplicate.status_code == existing.status_code == 409
        assert duplicate.text == existing.text
        assert "set-cookie" not in duplicate.headers
        assert "learner@example.com" not in duplicate.text
        assert not other.cookies.get(pages._APPLICATION_COOKIE)
    assert count(repo, "pending_registrations") == 1
    assert count(repo, "users") == 1
    assert count(repo, "user_passwords") == 0


def test_storage_failure_rolls_back_and_valid_form_can_retry(setup):
    _, repo, client, _ = setup
    with repo._connect() as connection:
        connection.execute(
            "CREATE TRIGGER fail_save BEFORE INSERT ON registration_browser_bindings BEGIN SELECT RAISE(FAIL, 'private-db-location'); END"
        )
    failed = submit(client)
    # Integrity failures use the same private unavailable-application result.
    assert failed.status_code == 409
    assert "private-db-location" not in failed.text
    assert not client.cookies.get(pages._APPLICATION_COOKIE)
    assert count(repo, "pending_registrations") == 0
    with repo._connect() as connection:
        connection.execute("DROP TRIGGER fail_save")
    assert submit(client).status_code == 303


def test_database_unavailable_never_sets_owner_cookie_or_exposes_error(
    setup, monkeypatch
):
    _, _, client, _ = setup

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("private-db-location-and-password")

    monkeypatch.setattr(pages, "begin_browser_registration", fail)
    response = submit(client)
    assert response.status_code == 503
    assert "private-db" not in response.text
    assert PASSWORD not in response.text
    assert not client.cookies.get(pages._APPLICATION_COOKIE)


def test_hash_work_is_bounded_and_busy_response_can_be_retried(setup, monkeypatch):
    app, repo, client, directory = setup

    # Rebuild with an occupied hash gate; no hashing or draft insert is allowed.
    class Gate:
        busy = True

        def acquire(self, *, blocking):
            assert blocking is False
            return not self.busy

        def release(self):
            pass

    gate = Gate()
    monkeypatch.setattr(pages, "BoundedSemaphore", lambda limit: gate)
    rebuilt = make_app(directory)
    with TestClient(rebuilt, base_url="https://coach.example.com") as other:
        busy = submit(other)
        assert busy.status_code == 503 and busy.headers["retry-after"] == "2"
        assert count(repo, "pending_registrations") == 0
        gate.busy = False
        assert submit(other).status_code == 303


def test_existing_owner_storage_failure_does_not_create_another_application(
    setup, monkeypatch
):
    _, repo, client, _ = setup
    submit(client)
    cookie = client.cookies.get(pages._APPLICATION_COOKIE)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("private-location")

    monkeypatch.setattr(pages, "get_browser_registration_status", fail)
    assert client.get(PATH).status_code == 503
    assert submit(client).status_code == 503
    assert count(repo, "pending_registrations") == 1
    assert client.cookies.get(pages._APPLICATION_COOKIE) == cookie


def test_saved_application_can_still_be_confirmed_only_with_an_internal_mail_link(
    setup,
):
    _, repo, client, _ = setup
    submit(client)
    request_id, secret = client.cookies.get(pages._APPLICATION_COOKIE).split(".")
    message = issue_registration_verification(
        repo,
        request_id,
        "https://coach.example.com/web/verify-registration",
        browser_secret=secret,
    )
    confirmation = Inputs(client.get(message.activation_url).text).values
    assert client.post("/web/verify-registration", data=confirmation).status_code == 200
    assert repo.is_email_verified(repo.get_by_email("learner@example.com").user_id)
    assert client.get(PATH).status_code == 403
    assert count(repo, "registration_browser_bindings") == 0


def test_concurrent_first_submissions_never_replace_a_saved_application(setup):
    app, repo, client, _ = setup
    form_token = csrf(client)
    cookie = client.cookies.get(pages._COOKIE)
    barrier = Barrier(2)

    def attempt(index):
        with TestClient(app, base_url="https://coach.example.com") as other:
            other.cookies.set(pages._COOKIE, cookie)
            barrier.wait(timeout=10)
            response = other.post(
                "/web/auth/register",
                data={
                    "csrf": form_token,
                    "email": "learner@example.com",
                    "password": PASSWORD + str(index),
                },
                follow_redirects=False,
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert sorted(results) == [303, 409]
    assert (
        count(repo, "pending_registrations")
        == count(repo, "registration_browser_bindings")
        == 1
    )
    assert count(repo, "users") == 0
