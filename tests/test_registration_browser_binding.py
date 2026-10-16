import hashlib
import re
import smtplib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from threading import Barrier
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from security.auth import verify_user_password
from security.email_verification import (
    confirm_registration_verification,
    issue_registration_verification,
)
from security.pending_registration import (
    PendingRegistrationUnavailable,
    begin_browser_registration,
    begin_pending_registration,
    get_browser_registration,
    get_pending_registration,
)
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


NOW = datetime(2026, 10, 16, 8, tzinfo=timezone.utc)
PASSWORD = " a quiet registration phrase "
URL = "https://coach.example.com/web/verify-registration"


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("browser binding must never contact SMTP")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)


@pytest.fixture
def repository(tmp_path):
    return SQLiteUserRepository(tmp_path / "users.db")


def begin(repository, **changes):
    fields = dict(
        name="成长者", email="learner@example.com", password=PASSWORD, now=NOW
    )
    fields.update(changes)
    return begin_browser_registration(repository, **fields)


def status(repository, receipt, *, now=NOW):
    return get_browser_registration(
        repository, receipt.request_id, receipt.browser_secret, now=now
    )


def issue(repository, receipt, *, now=NOW, secret=None):
    return issue_registration_verification(
        repository,
        receipt.request_id,
        URL,
        browser_secret=receipt.browser_secret if secret is None else secret,
        now=now,
    )


def token(message):
    return parse_qs(urlsplit(message.activation_url).query)["token"][0]


def rows(repository, table):
    assert table in {
        "pending_registrations",
        "registration_browser_bindings",
        "registration_email_verifications",
        "users",
        "user_passwords",
    }
    with sqlite3.connect(repository.database_path) as connection:
        return connection.execute(f"SELECT * FROM {table}").fetchall()


def test_new_draft_binding_is_atomic_hashed_redacted_and_minimal(repository, capsys):
    receipt = begin(repository)
    assert len(receipt.browser_secret) == 43
    binding = rows(repository, "registration_browser_bindings")
    digest = hashlib.sha256(
        b"registration-browser\0" + receipt.browser_secret.encode()
    ).hexdigest()
    assert binding == [(receipt.request_id, digest)]
    assert receipt.browser_secret.encode() not in repository.database_path.read_bytes()
    assert PASSWORD.encode() not in repository.database_path.read_bytes()
    assert receipt.browser_secret not in repr(receipt)
    assert receipt.request_id not in repr(receipt)
    result = status(repository, receipt)
    assert set(asdict(result)) == {"request_id", "expires_at"}
    assert result.expires_at == receipt.expires_at == NOW + timedelta(hours=1)
    assert "password" not in repr(result)
    assert rows(repository, "users") == []
    assert rows(repository, "user_passwords") == []
    assert rows(repository, "registration_email_verifications") == []
    assert get_pending_registration(repository, receipt.request_id, now=NOW) is None
    assert capsys.readouterr().out == ""


def test_id_alone_cannot_query_or_issue_for_a_bound_draft(repository):
    receipt = begin(repository)
    assert (
        get_browser_registration(repository, receipt.request_id, None, now=NOW) is None
    )
    with pytest.raises(ValueError, match="^registration verification unavailable$"):
        issue_registration_verification(repository, receipt.request_id, URL, now=NOW)
    assert rows(repository, "registration_email_verifications") == []
    assert status(repository, receipt) is not None


@pytest.mark.parametrize(
    "secret", [None, "", 1, "a" * 42, "a" * 44, "字" * 43, "!" * 43, "a" * 43]
)
def test_bad_or_foreign_secret_is_generic_and_does_not_replace_links(
    repository, secret
):
    receipt = begin(repository)
    original = issue(repository, receipt)
    before = rows(repository, "registration_email_verifications")
    assert (
        get_browser_registration(repository, receipt.request_id, secret, now=NOW)
        is None
    )
    with pytest.raises(ValueError, match="^registration verification unavailable$"):
        issue_registration_verification(
            repository,
            receipt.request_id,
            URL,
            browser_secret=secret,
            now=NOW + timedelta(seconds=60),
        )
    assert rows(repository, "registration_email_verifications") == before
    assert (
        confirm_registration_verification(repository, token(original), now=NOW)
        is not None
    )


def test_two_browsers_cannot_swap_receipts_or_use_email_token_as_browser_secret(
    repository,
):
    first = begin(repository)
    second = begin(repository, email="second@example.com")
    assert first.browser_secret != second.browser_secret
    assert (
        get_browser_registration(
            repository, first.request_id, second.browser_secret, now=NOW
        )
        is None
    )
    with pytest.raises(ValueError):
        issue(repository, first, secret=second.browser_secret)
    message = issue(repository, first)
    assert (
        get_browser_registration(repository, first.request_id, token(message), now=NOW)
        is None
    )
    assert (
        confirm_registration_verification(repository, first.browser_secret, now=NOW)
        is None
    )
    assert status(repository, first) is not None
    assert status(repository, second) is not None


def test_binding_survives_restart_and_successful_confirmation_cleans_it(repository):
    receipt = begin(repository)
    restored = SQLiteUserRepository(repository.database_path)
    assert status(restored, receipt).expires_at == receipt.expires_at
    message = issue(restored, receipt)
    user_id = confirm_registration_verification(restored, token(message), now=NOW)
    assert restored.is_email_verified(user_id)
    assert verify_user_password(restored, user_id, PASSWORD)
    assert status(restored, receipt) is None
    assert rows(restored, "pending_registrations") == []
    assert rows(restored, "registration_browser_bindings") == []
    assert rows(restored, "registration_email_verifications") == []
    with pytest.raises(ValueError):
        issue(restored, receipt, now=NOW + timedelta(seconds=60))


@pytest.mark.parametrize(
    "seconds,active",
    [(-1, False), (0, True), (3599, True), (3600, False), (3601, False)],
)
def test_binding_uses_original_draft_lifetime_without_extension(
    repository, seconds, active
):
    receipt = begin(repository)
    issue(repository, receipt)
    result = status(repository, receipt, now=NOW + timedelta(seconds=seconds))
    assert (result is not None) is active
    if result is not None:
        assert result.expires_at == receipt.expires_at
    if seconds >= 3600:
        assert rows(repository, "registration_browser_bindings") == []
        assert rows(repository, "registration_email_verifications") == []
    if seconds < 0:
        assert status(repository, receipt) is not None


def test_resend_is_owner_checked_and_keeps_cooldown_expiry_and_single_use(repository):
    receipt = begin(repository)
    first = issue(repository, receipt)
    with pytest.raises(ValueError):
        issue(repository, receipt, now=NOW + timedelta(seconds=59))
    latest = issue(repository, receipt, now=NOW + timedelta(seconds=60))
    assert latest.expires_at == first.expires_at == receipt.expires_at
    assert (
        confirm_registration_verification(
            repository, token(first), now=NOW + timedelta(seconds=60)
        )
        is None
    )
    assert (
        confirm_registration_verification(
            repository, token(latest), now=NOW + timedelta(seconds=60)
        )
        is not None
    )


def test_duplicate_draft_cannot_steal_existing_browser_binding(repository):
    receipt = begin(repository)
    before = (
        rows(repository, "pending_registrations"),
        rows(repository, "registration_browser_bindings"),
    )
    with pytest.raises(PendingRegistrationUnavailable):
        begin(repository, name="另一个人", password="a different registration phrase")
    assert before == (
        rows(repository, "pending_registrations"),
        rows(repository, "registration_browser_bindings"),
    )
    assert status(repository, receipt) is not None


def test_concurrent_same_email_has_exactly_one_draft_and_matching_binding(repository):
    barrier = Barrier(2)

    def create():
        barrier.wait(timeout=10)
        try:
            return begin(repository)
        except PendingRegistrationUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create(), range(2)))
    receipts = [value for value in results if value is not None]
    assert len(receipts) == 1
    assert len(rows(repository, "pending_registrations")) == 1
    assert len(rows(repository, "registration_browser_bindings")) == 1
    assert status(repository, receipts[0]) is not None


def test_binding_insert_failure_rolls_back_draft_and_allows_retry(repository):
    with repository._connect() as connection:
        connection.execute(
            "CREATE TRIGGER fail_binding BEFORE INSERT ON registration_browser_bindings BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"
        )
    with pytest.raises(PendingRegistrationUnavailable):
        begin(repository)
    assert rows(repository, "pending_registrations") == []
    assert rows(repository, "registration_browser_bindings") == []
    with repository._connect() as connection:
        connection.execute("DROP TRIGGER fail_binding")
    assert status(repository, begin(repository)) is not None


def test_confirmation_failure_restores_binding_link_and_draft_for_retry(repository):
    receipt = begin(repository)
    message = issue(repository, receipt)
    before = rows(repository, "registration_browser_bindings")
    with repository._connect() as connection:
        connection.execute(
            "CREATE TRIGGER fail_binding_delete BEFORE DELETE ON registration_browser_bindings BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        confirm_registration_verification(repository, token(message), now=NOW)
    assert rows(repository, "users") == []
    assert rows(repository, "user_passwords") == []
    assert rows(repository, "registration_browser_bindings") == before
    assert status(repository, receipt) is not None
    with repository._connect() as connection:
        connection.execute("DROP TRIGGER fail_binding_delete")
    assert (
        confirm_registration_verification(repository, token(message), now=NOW)
        is not None
    )


def test_replacement_after_expiry_has_fresh_secret_and_old_secret_cannot_claim_it(
    repository,
):
    first = begin(repository)
    issue(repository, first)
    second = begin(repository, now=first.expires_at)
    assert first.request_id != second.request_id
    assert first.browser_secret != second.browser_secret
    assert (
        get_browser_registration(
            repository, second.request_id, first.browser_secret, now=first.expires_at
        )
        is None
    )
    assert len(rows(repository, "registration_browser_bindings")) == 1
    assert rows(repository, "registration_email_verifications") == []
    assert status(repository, second, now=first.expires_at) is not None


def test_legacy_unbound_draft_is_not_claimable_by_an_arbitrary_browser(repository):
    legacy = begin_pending_registration(
        repository, email="legacy@example.com", password=PASSWORD, now=NOW
    )
    assert (
        get_browser_registration(repository, legacy.request_id, "a" * 43, now=NOW)
        is None
    )
    with pytest.raises(ValueError):
        issue_registration_verification(
            repository, legacy.request_id, URL, browser_secret="a" * 43, now=NOW
        )
    assert get_pending_registration(repository, legacy.request_id, now=NOW) is not None
    assert issue_registration_verification(repository, legacy.request_id, URL, now=NOW)


def test_other_flow_creating_account_cleans_binding_without_overwriting_user(
    repository,
):
    receipt = begin(repository)
    message = issue(repository, receipt)
    original = User(name="旧账户", email=" LEARNER@EXAMPLE.COM ")
    repository.save(original)
    assert status(repository, receipt) is None
    assert rows(repository, "registration_browser_bindings") == []
    assert (
        confirm_registration_verification(repository, token(message), now=NOW) is None
    )
    assert repository.get_by_id(original.user_id) == original
    assert repository.get_password_hash(original.user_id) is None


def test_invalid_secret_and_id_do_not_query_repository(repository, monkeypatch):
    def forbidden(*args):
        raise AssertionError("malformed input must not query storage")

    monkeypatch.setattr(repository, "get_browser_registration", forbidden)
    assert get_browser_registration(repository, "bad", "a" * 43, now=NOW) is None
    assert (
        get_browser_registration(repository, "registration_" + "a" * 32, "bad", now=NOW)
        is None
    )


def test_naive_time_is_rejected_and_timezone_equivalent_is_supported(repository):
    receipt = begin(repository)
    with pytest.raises(ValueError, match="timezone"):
        status(repository, receipt, now=NOW.replace(tzinfo=None))
    assert (
        status(repository, receipt, now=NOW.astimezone(timezone(timedelta(hours=8))))
        is not None
    )


def test_web_preview_never_binds_or_saves_an_application(tmp_path):
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    repository = SQLiteUserRepository(tmp_path / "users.db")
    with TestClient(app) as client:
        page = client.get("/web/register")
        csrf = re.search(r'name="csrf" value="([A-Za-z0-9_-]{43})"', page.text).group(1)
        response = client.post(
            "/web/auth/register",
            data={"csrf": csrf, "email": "preview@example.com", "password": PASSWORD},
        )
        assert response.status_code == 200
    assert rows(repository, "pending_registrations") == []
    assert rows(repository, "registration_browser_bindings") == []


def test_confirmation_link_can_be_explicitly_confirmed_in_another_browser(
    repository, tmp_path
):
    now = datetime.now(timezone.utc)
    receipt = begin(repository, now=now)
    message = issue(repository, receipt, now=now)
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app, base_url="https://coach.example.com") as other:
        page = other.get(message.activation_url)
        csrf = re.search(r'name="csrf" value="([A-Za-z0-9_-]{43})"', page.text).group(1)
        assert (
            other.post(
                "/web/verify-registration", data={"token": token(message), "csrf": csrf}
            ).status_code
            == 200
        )
    assert repository.is_email_verified(
        repository.get_by_email("learner@example.com").user_id
    )
    assert rows(repository, "registration_browser_bindings") == []


def test_failed_secret_generation_cannot_fall_back_to_unbound_draft(
    repository, monkeypatch
):
    monkeypatch.setattr(
        "security.pending_registration.secrets.token_urlsafe", lambda size: "invalid"
    )
    with pytest.raises(PendingRegistrationUnavailable):
        begin(repository)
    assert rows(repository, "pending_registrations") == []


def test_duplicate_secret_rolls_back_new_draft_without_replacing_original_binding(
    repository, monkeypatch
):
    monkeypatch.setattr(
        "security.pending_registration.secrets.token_urlsafe", lambda size: "a" * 43
    )
    original = begin(repository)
    with pytest.raises(PendingRegistrationUnavailable):
        begin(repository, email="different@example.com")
    assert len(rows(repository, "pending_registrations")) == 1
    assert len(rows(repository, "registration_browser_bindings")) == 1
    assert status(repository, original) is not None
