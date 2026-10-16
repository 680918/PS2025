import hashlib
import smtplib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from urllib.parse import parse_qs, urlsplit

import pytest

from security.auth import initialize_user_password, verify_user_password
from security.email_verification import (
    confirm_email_verification,
    confirm_registration_verification,
    issue_email_verification,
    issue_registration_verification,
)
from security.pending_registration import (
    begin_pending_registration,
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
        raise AssertionError("internal registration must not contact SMTP")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)


@pytest.fixture
def repository(tmp_path):
    return SQLiteUserRepository(tmp_path / "users.db")


def begin(repository, **changes):
    fields = dict(
        name="测试成长者", email="learner@example.com", password=PASSWORD, now=NOW
    )
    fields.update(changes)
    return begin_pending_registration(repository, **fields)


def issue(repository, receipt, now=NOW, url=URL):
    return issue_registration_verification(repository, receipt.request_id, url, now=now)


def token_from(message):
    return parse_qs(urlsplit(message.activation_url).query)["token"][0]


def count(repository, table):
    assert table in {
        "users",
        "user_passwords",
        "user_email_verifications",
        "pending_registrations",
        "registration_email_verifications",
    }
    with sqlite3.connect(repository.database_path) as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_verified_registration_survives_restart_and_keeps_exact_password_hash(
    repository, capsys
):
    receipt = begin(repository, email="  Learner@Example.COM ")
    draft = get_pending_registration(repository, receipt.request_id, now=NOW)
    message = issue(repository, receipt)
    token = token_from(message)
    assert message.recipient == "learner@example.com"
    assert message.expires_at == receipt.expires_at
    assert urlsplit(message.activation_url).path == "/web/verify-registration"
    assert len(token) == 43
    assert token not in repr(message)
    assert message.recipient not in repr(message)
    for table in ("users", "user_passwords", "user_email_verifications"):
        assert count(repository, table) == 0
    with sqlite3.connect(repository.database_path) as connection:
        stored = connection.execute(
            "SELECT token_hash FROM registration_email_verifications"
        ).fetchone()[0]
    assert stored == hashlib.sha256(b"registration\0" + token.encode()).hexdigest()
    assert token.encode() not in repository.database_path.read_bytes()
    assert PASSWORD.encode() not in repository.database_path.read_bytes()
    assert confirm_email_verification(repository, token, now=NOW) is None
    assert (
        confirm_registration_verification(repository, receipt.request_id, now=NOW)
        is None
    )

    restored = SQLiteUserRepository(repository.database_path)
    user_id = confirm_registration_verification(
        restored, token, now=NOW + timedelta(seconds=2)
    )
    assert user_id is not None and user_id != receipt.request_id
    user = restored.get_by_id(user_id)
    assert user.name == "测试成长者"
    assert user.email == message.recipient
    assert restored.get_password_hash(user_id) == draft.password_hash
    assert restored.is_email_verified(user_id)
    assert verify_user_password(restored, user_id, PASSWORD)
    assert not verify_user_password(restored, user_id, PASSWORD.strip())
    assert (
        confirm_registration_verification(
            restored, token, now=NOW + timedelta(seconds=3)
        )
        is None
    )
    for table in ("users", "user_passwords", "user_email_verifications"):
        assert count(restored, table) == 1
    assert count(restored, "pending_registrations") == 0
    assert count(restored, "registration_email_verifications") == 0
    with sqlite3.connect(restored.database_path) as connection:
        assert connection.execute(
            "SELECT token_hash, verified_at FROM user_email_verifications WHERE user_id = ?",
            (user_id,),
        ).fetchone() == (None, int(NOW.timestamp()) + 2)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "seconds,accepted",
    [(-1, False), (0, True), (3599, True), (3600, False), (3601, False)],
)
def test_confirmation_time_boundaries(repository, seconds, accepted):
    receipt = begin(repository)
    token = token_from(issue(repository, receipt))
    result = confirm_registration_verification(
        repository, token, now=NOW + timedelta(seconds=seconds)
    )
    assert (result is not None) is accepted
    assert count(repository, "users") == int(accepted)
    if seconds >= 3600:
        assert count(repository, "pending_registrations") == 0
        assert count(repository, "registration_email_verifications") == 0
    if seconds < 0:
        assert confirm_registration_verification(repository, token, now=NOW) is not None


@pytest.mark.parametrize("seconds", [-1, 3600, 3601])
def test_unavailable_draft_cannot_issue_a_link(repository, seconds):
    receipt = begin(repository)
    with pytest.raises(ValueError, match="^registration verification unavailable$"):
        issue(repository, receipt, now=NOW + timedelta(seconds=seconds))
    assert count(repository, "registration_email_verifications") == 0
    assert count(repository, "users") == 0


def test_resend_cooldown_keeps_previous_link_and_lifetime(repository):
    receipt = begin(repository)
    before = get_pending_registration(repository, receipt.request_id, now=NOW)
    first = issue(repository, receipt)
    with pytest.raises(ValueError, match="registration verification unavailable"):
        issue(repository, receipt, now=NOW + timedelta(seconds=59))
    second = issue(repository, receipt, now=NOW + timedelta(seconds=60))
    assert token_from(first) != token_from(second)
    assert second.expires_at == receipt.expires_at
    assert (
        get_pending_registration(
            repository, receipt.request_id, now=NOW + timedelta(seconds=60)
        )
        == before
    )
    assert (
        confirm_registration_verification(
            repository, token_from(first), now=NOW + timedelta(seconds=60)
        )
        is None
    )
    assert (
        confirm_registration_verification(
            repository, token_from(second), now=NOW + timedelta(seconds=60)
        )
        is not None
    )


def test_blocked_resend_does_not_consume_original_link(repository):
    receipt = begin(repository)
    first = issue(repository, receipt)
    with pytest.raises(ValueError):
        issue(repository, receipt, now=NOW + timedelta(seconds=30))
    assert (
        confirm_registration_verification(
            repository, token_from(first), now=NOW + timedelta(seconds=31)
        )
        is not None
    )


def test_late_issuance_and_resend_never_extend_draft_expiry(repository):
    receipt = begin(repository)
    message = issue(repository, receipt, now=NOW + timedelta(seconds=3539))
    latest = issue(repository, receipt, now=NOW + timedelta(seconds=3599))
    assert message.expires_at == latest.expires_at == receipt.expires_at
    assert (
        confirm_registration_verification(
            repository, token_from(latest), now=receipt.expires_at
        )
        is None
    )


def test_token_cannot_be_used_before_its_issuance(repository):
    receipt = begin(repository)
    message = issue(repository, receipt, now=NOW + timedelta(seconds=30))
    assert (
        confirm_registration_verification(
            repository, token_from(message), now=NOW + timedelta(seconds=29)
        )
        is None
    )
    assert (
        confirm_registration_verification(
            repository, token_from(message), now=NOW + timedelta(seconds=30)
        )
        is not None
    )


@pytest.mark.parametrize(
    "token", [None, 17, "", "x" * 42, "x" * 44, "!" * 43, "x" * 43, "x" * 42 + "\n"]
)
def test_wrong_tokens_never_create_or_consume(repository, token):
    receipt = begin(repository)
    message = issue(repository, receipt)
    assert confirm_registration_verification(repository, token, now=NOW) is None
    assert count(repository, "users") == 0
    assert (
        confirm_registration_verification(repository, token_from(message), now=NOW)
        is not None
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://coach.example.com/verify",
        "https://evil@example.com/verify",
        "https://coach.example.com/verify?next=bad",
        "https://coach.example.com/verify#bad",
        "//coach.example.com/verify",
        "https://coach.example.com/\r\n",
    ],
)
def test_invalid_configured_url_cannot_issue(repository, url):
    receipt = begin(repository)
    with pytest.raises(ValueError, match="invalid configured activation URL"):
        issue(repository, receipt, url=url)
    assert count(repository, "registration_email_verifications") == 0


def test_loopback_url_is_allowed_for_future_local_preview(repository):
    receipt = begin(repository)
    message = issue(
        repository, receipt, url="http://127.0.0.1:8776/web/verify-registration"
    )
    assert message.activation_url.startswith(
        "http://127.0.0.1:8776/web/verify-registration?token="
    )


@pytest.mark.parametrize(
    "request_id",
    [
        None,
        "",
        "registration_" + "f" * 31,
        "registration_" + "f" * 33,
        "unknown",
        "registration_" + "f" * 32,
    ],
)
def test_unknown_or_invalid_request_id_is_generic(repository, request_id):
    with pytest.raises(ValueError, match="^registration verification unavailable$"):
        issue_registration_verification(repository, request_id, URL, now=NOW)
    assert count(repository, "registration_email_verifications") == 0


def test_timezone_rules_and_missing_timezone_cannot_consume_link(repository):
    receipt = begin(repository)
    with pytest.raises(ValueError, match="timezone"):
        issue(repository, receipt, now=NOW.replace(tzinfo=None))
    assert count(repository, "registration_email_verifications") == 0
    china_time = NOW.astimezone(timezone(timedelta(hours=8)))
    message = issue(repository, receipt, now=china_time)
    with pytest.raises(ValueError, match="timezone"):
        confirm_registration_verification(
            repository, token_from(message), now=NOW.replace(tzinfo=None)
        )
    assert (
        confirm_registration_verification(
            repository, token_from(message), now=china_time
        )
        is not None
    )


def test_existing_user_link_cannot_create_a_new_account(repository):
    user = User(name="原用户", email="old@example.com")
    repository.save(user)
    old = issue_email_verification(
        repository, user.user_id, "https://coach.example.com/web/verify-email", now=NOW
    )
    receipt = begin(repository)
    new = issue(repository, receipt)
    assert (
        confirm_registration_verification(repository, token_from(old), now=NOW) is None
    )
    assert count(repository, "users") == 1
    assert confirm_email_verification(repository, token_from(new), now=NOW) is None
    assert (
        confirm_email_verification(repository, token_from(old), now=NOW) == user.user_id
    )
    assert (
        confirm_registration_verification(repository, token_from(new), now=NOW)
        != user.user_id
    )
    assert count(repository, "users") == 2


def test_identical_random_values_are_separated_between_two_token_flows(
    repository, monkeypatch
):
    monkeypatch.setattr(
        "security.email_verification.secrets.token_urlsafe", lambda size: "x" * 43
    )
    user = User(name="原用户", email="old@example.com")
    repository.save(user)
    old = issue_email_verification(
        repository, user.user_id, "https://coach.example.com/web/verify-email", now=NOW
    )
    receipt = begin(repository)
    new = issue(repository, receipt)
    assert token_from(new) == token_from(old)
    with sqlite3.connect(repository.database_path) as connection:
        old_hash = connection.execute(
            "SELECT token_hash FROM user_email_verifications"
        ).fetchone()[0]
        new_hash = connection.execute(
            "SELECT token_hash FROM registration_email_verifications"
        ).fetchone()[0]
    assert old_hash != new_hash


@pytest.mark.parametrize("email", ["learner@example.com", " LEARNER@EXAMPLE.COM "])
def test_account_created_by_other_flow_is_never_overwritten(repository, email):
    receipt = begin(repository)
    message = issue(repository, receipt)
    existing = User(name="原有账户", email=email)
    repository.save(existing)
    initialize_user_password(repository, existing.user_id, "original account password")
    old_message = issue_email_verification(
        repository,
        existing.user_id,
        "https://coach.example.com/web/verify-email",
        now=NOW,
    )
    assert (
        confirm_email_verification(repository, token_from(old_message), now=NOW)
        == existing.user_id
    )
    original_hash = repository.get_password_hash(existing.user_id)
    with pytest.raises(ValueError, match="registration verification unavailable"):
        issue(repository, receipt, now=NOW + timedelta(seconds=60))
    assert (
        confirm_registration_verification(repository, token_from(message), now=NOW)
        is None
    )
    assert repository.get_by_id(existing.user_id) == existing
    assert repository.get_password_hash(existing.user_id) == original_hash
    assert repository.is_email_verified(existing.user_id)
    assert count(repository, "users") == 1
    assert count(repository, "pending_registrations") == 0
    assert count(repository, "registration_email_verifications") == 0


def test_expired_draft_replacement_cascades_old_link_deletion(repository):
    first = begin(repository)
    old_message = issue(repository, first)
    replacement = begin(
        repository, password="a completely different password", now=first.expires_at
    )
    assert replacement.request_id != first.request_id
    assert count(repository, "registration_email_verifications") == 0
    assert (
        confirm_registration_verification(
            repository, token_from(old_message), now=first.expires_at
        )
        is None
    )
    message = issue(repository, replacement, now=first.expires_at)
    user_id = confirm_registration_verification(
        repository, token_from(message), now=first.expires_at
    )
    assert verify_user_password(repository, user_id, "a completely different password")
    assert not verify_user_password(repository, user_id, PASSWORD)


def test_reading_expired_draft_also_removes_its_verification_token(repository):
    receipt = begin(repository)
    issue(repository, receipt)
    assert (
        get_pending_registration(repository, receipt.request_id, now=receipt.expires_at)
        is None
    )
    assert count(repository, "registration_email_verifications") == 0


def test_concurrent_confirmation_creates_exactly_one_complete_account(repository):
    receipt = begin(repository)
    token = token_from(issue(repository, receipt))
    barrier = Barrier(2)

    def confirm():
        barrier.wait(timeout=10)
        return confirm_registration_verification(repository, token, now=NOW)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: confirm(), range(2)))
    user_ids = [value for value in results if value is not None]
    assert len(user_ids) == 1
    for table in ("users", "user_passwords", "user_email_verifications"):
        assert count(repository, table) == 1
    assert repository.is_email_verified(user_ids[0])
    assert verify_user_password(repository, user_ids[0], PASSWORD)
    assert count(repository, "registration_email_verifications") == 0


def test_concurrent_resend_has_one_winner_and_invalidates_previous_link(repository):
    receipt = begin(repository)
    first = issue(repository, receipt)
    barrier = Barrier(2)
    later = NOW + timedelta(seconds=60)

    def resend():
        barrier.wait(timeout=10)
        try:
            return issue(repository, receipt, now=later)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: resend(), range(2)))
    messages = [value for value in results if value is not None]
    assert len(messages) == 1
    assert (
        confirm_registration_verification(repository, token_from(first), now=later)
        is None
    )
    assert (
        confirm_registration_verification(
            repository, token_from(messages[0]), now=later
        )
        is not None
    )


@pytest.mark.parametrize(
    "table,operation",
    [
        ("users", "INSERT"),
        ("user_passwords", "INSERT"),
        ("user_email_verifications", "INSERT"),
        ("pending_registrations", "DELETE"),
    ],
)
def test_failure_at_each_write_rolls_back_everything_and_allows_retry(
    repository, table, operation
):
    receipt = begin(repository)
    token = token_from(issue(repository, receipt))
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            f"CREATE TRIGGER fail_registration BEFORE {operation} ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="simulated storage failure"):
        confirm_registration_verification(repository, token, now=NOW)
    for target in ("users", "user_passwords", "user_email_verifications"):
        assert count(repository, target) == 0
    assert count(repository, "pending_registrations") == 1
    assert count(repository, "registration_email_verifications") == 1
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("DROP TRIGGER fail_registration")
    assert confirm_registration_verification(repository, token, now=NOW) is not None


def test_token_collision_rolls_back_without_replacing_other_draft(
    repository, monkeypatch
):
    monkeypatch.setattr(
        "security.email_verification.secrets.token_urlsafe", lambda size: "x" * 43
    )
    first = begin(repository)
    first_message = issue(repository, first)
    second = begin(repository, email="second@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        issue(repository, second)
    assert count(repository, "pending_registrations") == 2
    assert count(repository, "registration_email_verifications") == 1
    assert (
        confirm_registration_verification(
            repository, token_from(first_message), now=NOW
        )
        is not None
    )
    assert repository.get_by_email("second@example.com") is None
