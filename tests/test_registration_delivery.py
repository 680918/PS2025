import smtplib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from threading import Event
from urllib.parse import parse_qs, urlsplit

import pytest

import security.registration_delivery as delivery
from security.email_verification import (
    confirm_registration_verification,
    issue_registration_verification,
)
from security.pending_registration import (
    begin_browser_registration,
    begin_pending_registration,
    get_browser_registration,
)
from security.verification_mailer import (
    MailConfigurationError,
    MailDeliveryError,
    SMTPSettings,
)
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


NOW = datetime(2026, 10, 16, 8, tzinfo=timezone.utc)
URL = "https://coach.example.com/web/verify-registration"
PASSWORD = " a quiet registration phrase "
SETTINGS = SMTPSettings("sender@163.com", "fake-authorization-code")


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("no real SMTP in these tests")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    yield
    assert calls == []


@pytest.fixture
def repository(tmp_path):
    return SQLiteUserRepository(tmp_path / "users.db")


@pytest.fixture
def receipt(repository):
    return begin_browser_registration(
        repository,
        name="成长者",
        email="learner@example.com",
        password=PASSWORD,
        now=NOW,
    )


@pytest.fixture
def messages(monkeypatch):
    captured = []

    def accept(message, settings, *, now=None):
        assert settings == SETTINGS
        captured.append(message)

    monkeypatch.setattr(delivery, "send_verification_email", accept)
    return captured


def send(repository, receipt, **changes):
    fields = dict(browser_secret=receipt.browser_secret, now=NOW)
    fields.update(changes)
    return delivery.send_registration_verification(
        repository, receipt.request_id, URL, SETTINGS, **fields
    )


def status(repository, receipt, **changes):
    return delivery.get_registration_delivery_status(
        repository,
        receipt.request_id,
        receipt.browser_secret,
        now=changes.get("now", NOW),
    )


def rows(repository, table):
    assert table in {
        "registration_mail_deliveries",
        "registration_email_verifications",
        "users",
        "user_passwords",
        "pending_registrations",
        "registration_browser_bindings",
    }
    with sqlite3.connect(repository.database_path) as connection:
        return connection.execute(f"SELECT * FROM {table}").fetchall()


def token(message):
    return parse_qs(urlsplit(message.activation_url).query)["token"][0]


def test_saved_application_starts_not_sent_and_status_is_minimal(repository, receipt):
    result = status(repository, receipt)
    assert asdict(result) == {"state": "not_sent", "retry_after_seconds": 0}
    assert rows(repository, "registration_mail_deliveries") == []
    assert rows(repository, "registration_email_verifications") == []


def test_success_records_only_acceptance_and_preserves_original_account_creation(
    repository, receipt, messages, capsys
):
    assert send(repository, receipt).state == "accepted"
    assert status(repository, receipt).state == "accepted"
    assert len(messages) == 1
    message = messages[0]
    assert message.recipient == "learner@example.com"
    assert message.expires_at == receipt.expires_at
    assert rows(repository, "users") == rows(repository, "user_passwords") == []
    stored = repr(
        rows(repository, "registration_mail_deliveries")
        + rows(repository, "registration_email_verifications")
    )
    captured = capsys.readouterr()
    for secret in (
        PASSWORD,
        receipt.browser_secret,
        token(message),
        message.activation_url,
        SETTINGS.authorization_code,
    ):
        assert secret not in stored
        assert secret not in repr(status(repository, receipt))
        assert secret not in captured.out + captured.err
    user_id = confirm_registration_verification(repository, token(message), now=NOW)
    assert user_id is not None
    assert repository.is_email_verified(user_id)
    assert rows(repository, "registration_mail_deliveries") == []
    assert rows(repository, "pending_registrations") == []
    assert status(repository, receipt) is None
    assert (
        confirm_registration_verification(repository, token(message), now=NOW) is None
    )


@pytest.mark.parametrize(
    "code", ["authentication_failed", "recipient_refused", "rejected", "unsupported"]
)
def test_definite_failures_require_explicit_retry_and_cooldown(
    repository, receipt, messages, monkeypatch, code
):
    def fail(*args, **kwargs):
        raise MailDeliveryError(code, "private server response")

    monkeypatch.setattr(delivery, "send_verification_email", fail)
    assert send(repository, receipt).state == "failed"
    original = rows(repository, "registration_email_verifications")
    for args in (
        {"now": NOW + timedelta(seconds=60)},
        {"now": NOW + timedelta(seconds=59), "retry_failed": True},
    ):
        with pytest.raises(ValueError, match="unavailable"):
            send(repository, receipt, **args)
    assert rows(repository, "registration_email_verifications") == original
    monkeypatch.setattr(
        delivery,
        "send_verification_email",
        lambda message, *args, **kwargs: messages.append(message),
    )
    assert (
        send(
            repository, receipt, now=NOW + timedelta(seconds=60), retry_failed=True
        ).state
        == "accepted"
    )
    assert len(messages) == 1
    assert rows(repository, "registration_email_verifications") != original


@pytest.mark.parametrize(
    "code", ["timeout", "connection_failed", "tls_failed", "future_unknown_code"]
)
def test_uncertain_delivery_remains_locked_even_with_explicit_retry(
    repository, receipt, monkeypatch, code
):
    calls = []

    def uncertain(message, *args, **kwargs):
        calls.append(message)
        raise MailDeliveryError(code, "private raw SMTP response")

    monkeypatch.setattr(delivery, "send_verification_email", uncertain)
    assert send(repository, receipt).state == "unknown"
    assert status(repository, receipt).state == "unknown"
    reopened = SQLiteUserRepository(repository.database_path)
    for retry in (False, True):
        with pytest.raises(ValueError, match="unavailable"):
            send(
                reopened, receipt, now=NOW + timedelta(seconds=120), retry_failed=retry
            )
    assert len(calls) == 1
    # An uncertain SMTP result must not invalidate a possibly delivered link.
    assert (
        confirm_registration_verification(repository, token(calls[0]), now=NOW)
        is not None
    )


def test_accepted_delivery_and_legacy_issuer_cannot_invalidate_link(
    repository, receipt, messages
):
    send(repository, receipt)
    original = rows(repository, "registration_email_verifications")
    for retry in (False, True):
        with pytest.raises(ValueError, match="unavailable"):
            send(
                repository, receipt, now=NOW + timedelta(seconds=60), retry_failed=retry
            )
    with pytest.raises(ValueError, match="unavailable"):
        issue_registration_verification(
            repository,
            receipt.request_id,
            URL,
            browser_secret=receipt.browser_secret,
            now=NOW + timedelta(seconds=60),
        )
    assert rows(repository, "registration_email_verifications") == original
    assert len(messages) == 1


def test_concurrent_workers_claim_once_without_holding_database_during_smtp(
    repository, receipt, monkeypatch
):
    entered, release = Event(), Event()
    calls = []

    def blocked(message, *args, **kwargs):
        calls.append(message)
        entered.set()
        assert release.wait(10)

    monkeypatch.setattr(delivery, "send_verification_email", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(send, repository, receipt)
        try:
            assert entered.wait(10)
            second_repository = SQLiteUserRepository(repository.database_path)
            assert status(second_repository, receipt).state == "sending"
            # Even beyond the cooldown, an in-flight claim cannot be replaced.
            with pytest.raises(ValueError, match="unavailable"):
                send(second_repository, receipt, now=NOW + timedelta(seconds=120))
            assert len(calls) == 1
        finally:
            release.set()
        assert worker.result(timeout=10).state == "accepted"


def test_crash_leaves_durable_claim_after_restart(repository, receipt, monkeypatch):
    def crash(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(delivery, "send_verification_email", crash)
    with pytest.raises(KeyboardInterrupt):
        send(repository, receipt)
    reopened = SQLiteUserRepository(repository.database_path)
    assert status(reopened, receipt).state == "sending"
    for retry in (False, True):
        with pytest.raises(ValueError, match="unavailable"):
            send(
                reopened, receipt, now=NOW + timedelta(seconds=120), retry_failed=retry
            )


def test_accepted_mail_with_failed_state_write_stays_locked(
    repository, receipt, messages, monkeypatch
):
    def cannot_save(*args):
        raise sqlite3.OperationalError("private path and SQL")

    monkeypatch.setattr(repository, "finish_registration_delivery", cannot_save)
    assert send(repository, receipt).state == "unknown"
    assert status(repository, receipt).state == "sending"
    with pytest.raises(ValueError, match="unavailable"):
        send(repository, receipt, now=NOW + timedelta(seconds=120), retry_failed=True)
    assert len(messages) == 1


def test_atomic_claim_failure_rolls_back_link_and_never_calls_sender(
    repository, receipt, messages
):
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("""CREATE TRIGGER reject_claim BEFORE INSERT ON registration_mail_deliveries
            BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        send(repository, receipt)
    assert messages == []
    assert rows(repository, "registration_mail_deliveries") == []
    assert rows(repository, "registration_email_verifications") == []


@pytest.mark.parametrize("secret", [None, "", "x" * 43, "malformed"])
def test_wrong_owner_cannot_read_send_or_change_state(
    repository, receipt, messages, secret
):
    assert (
        delivery.get_registration_delivery_status(
            repository, receipt.request_id, secret, now=NOW
        )
        is None
    )
    with pytest.raises(ValueError, match="unavailable"):
        send(repository, receipt, browser_secret=secret)
    assert messages == []
    assert rows(repository, "registration_mail_deliveries") == []


def test_unbound_draft_cannot_enter_managed_sending(repository, messages):
    unbound = begin_pending_registration(
        repository, name="成长者", email="other@example.com", password=PASSWORD, now=NOW
    )
    with pytest.raises(ValueError, match="unavailable"):
        delivery.send_registration_verification(
            repository,
            unbound.request_id,
            URL,
            SETTINGS,
            browser_secret="x" * 43,
            now=NOW,
        )
    assert messages == []


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://evil.example/verify?redirect=x",
        "http://external.example/verify",
        "javascript:bad",
    ],
)
def test_bad_configuration_never_claims_or_sends(
    repository, receipt, messages, bad_url
):
    with pytest.raises(ValueError):
        delivery.send_registration_verification(
            repository,
            receipt.request_id,
            bad_url,
            SETTINGS,
            browser_secret=receipt.browser_secret,
            now=NOW,
        )
    assert messages == []
    assert status(repository, receipt).state == "not_sent"


def test_disabled_mail_never_claims_or_sends(repository, receipt, messages):
    with pytest.raises(MailConfigurationError):
        delivery.send_registration_verification(
            repository,
            receipt.request_id,
            URL,
            None,
            browser_secret=receipt.browser_secret,
            now=NOW,
        )
    assert messages == []
    assert status(repository, receipt).state == "not_sent"


def test_unexpected_sender_error_is_sanitized_and_locked(
    repository, receipt, monkeypatch, capsys
):
    def fail(*args, **kwargs):
        raise RuntimeError("private raw SMTP response " + SETTINGS.authorization_code)

    monkeypatch.setattr(delivery, "send_verification_email", fail)
    result = send(repository, receipt)
    assert asdict(result) == {"state": "unknown", "retry_after_seconds": 0}
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_message_validation_failure_is_retryable_but_not_automatically_retried(
    repository, receipt, monkeypatch
):
    calls = []

    def invalid(*args, **kwargs):
        calls.append(True)
        raise MailConfigurationError("invalid template")

    monkeypatch.setattr(delivery, "send_verification_email", invalid)
    assert send(repository, receipt).state == "failed"
    assert calls == [True]


def test_retry_never_extends_parent_expiry_and_old_worker_cannot_finish_it(
    repository, receipt, messages, monkeypatch
):
    def fail(*args, **kwargs):
        raise MailDeliveryError("rejected", "refused")

    monkeypatch.setattr(delivery, "send_verification_email", fail)
    send(repository, receipt)
    old_id = rows(repository, "registration_mail_deliveries")[0][1]
    monkeypatch.setattr(
        delivery,
        "send_verification_email",
        lambda message, *args, **kwargs: messages.append(message),
    )
    assert (
        send(
            repository, receipt, now=NOW + timedelta(seconds=3599), retry_failed=True
        ).state
        == "accepted"
    )
    assert messages[0].expires_at == receipt.expires_at
    assert not repository.finish_registration_delivery(
        receipt.request_id, old_id, "failed"
    )
    assert (
        status(repository, receipt, now=NOW + timedelta(seconds=3599)).state
        == "accepted"
    )


def test_expired_draft_cleanup_cascades_delivery_and_existing_users_unchanged(
    repository, receipt, messages
):
    existing = User(
        user_id="existing-user", name="原用户", email="existing@example.com"
    )
    repository.save(existing)
    original = rows(repository, "users")
    send(repository, receipt)
    assert status(repository, receipt, now=NOW + timedelta(hours=1)) is None
    with pytest.raises(ValueError, match="unavailable"):
        send(repository, receipt, now=NOW + timedelta(hours=1))
    assert (
        get_browser_registration(
            repository,
            receipt.request_id,
            receipt.browser_secret,
            now=NOW + timedelta(hours=1),
        )
        is None
    )
    assert rows(repository, "registration_mail_deliveries") == []
    assert rows(repository, "registration_email_verifications") == []
    assert rows(repository, "users") == original
    assert len(messages) == 1


def test_retry_flag_cannot_be_used_for_first_send(repository, receipt, messages):
    with pytest.raises(ValueError, match="unavailable"):
        send(repository, receipt, retry_failed=True)
    assert messages == []
    assert status(repository, receipt).state == "not_sent"


def test_failed_attempt_retry_replaces_link_only_after_explicit_authorized_action(
    repository, receipt, messages, monkeypatch
):
    def refused(message, *args, **kwargs):
        messages.append(message)
        raise MailDeliveryError("rejected", "private server response")

    monkeypatch.setattr(delivery, "send_verification_email", refused)
    assert send(repository, receipt).state == "failed"
    old_link = rows(repository, "registration_email_verifications")
    with pytest.raises(ValueError, match="unavailable"):
        send(
            repository,
            receipt,
            browser_secret="x" * 43,
            retry_failed=True,
            now=NOW + timedelta(seconds=60),
        )
    assert rows(repository, "registration_email_verifications") == old_link
    assert status(repository, receipt).state == "failed"
    monkeypatch.setattr(
        delivery,
        "send_verification_email",
        lambda message, *args, **kwargs: messages.append(message),
    )
    assert (
        send(
            repository, receipt, retry_failed=True, now=NOW + timedelta(seconds=60)
        ).state
        == "accepted"
    )
    assert len(messages) == 2
    assert (
        confirm_registration_verification(
            repository, token(messages[0]), now=NOW + timedelta(seconds=60)
        )
        is None
    )
    assert (
        confirm_registration_verification(
            repository, token(messages[1]), now=NOW + timedelta(seconds=60)
        )
        is not None
    )


def test_confirming_delivered_link_during_send_does_not_recreate_deleted_state(
    repository, receipt, monkeypatch
):
    # A fast user can click while the sender is still finishing its SMTP session.
    def accept_and_confirm(message, *args, **kwargs):
        assert (
            confirm_registration_verification(repository, token(message), now=NOW)
            is not None
        )

    monkeypatch.setattr(delivery, "send_verification_email", accept_and_confirm)
    assert send(repository, receipt).state == "unknown"
    assert len(rows(repository, "users")) == 1
    assert rows(repository, "registration_mail_deliveries") == []
    assert status(repository, receipt) is None
    with pytest.raises(ValueError, match="unavailable"):
        send(repository, receipt, now=NOW + timedelta(seconds=60))


def test_failed_retry_storage_error_preserves_previous_failure_and_link(
    repository, receipt, messages, monkeypatch
):
    def refused(*args, **kwargs):
        raise MailDeliveryError("rejected", "refused")

    monkeypatch.setattr(delivery, "send_verification_email", refused)
    assert send(repository, receipt).state == "failed"
    original_link = rows(repository, "registration_email_verifications")
    original_delivery = rows(repository, "registration_mail_deliveries")
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("""CREATE TRIGGER reject_retry BEFORE UPDATE ON registration_mail_deliveries
            BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        send(repository, receipt, retry_failed=True, now=NOW + timedelta(seconds=60))
    assert rows(repository, "registration_email_verifications") == original_link
    assert rows(repository, "registration_mail_deliveries") == original_delivery
    assert messages == []
