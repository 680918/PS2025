import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from security.email_verification import (
    issue_email_verification,
    confirm_email_verification,
)
from security.login_sessions import (
    sign_in,
    sign_out,
    signed_in_account,
    session_token_hash,
)
from security.passwords import hash_password
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


NOW = datetime(2026, 10, 16, 8, tzinfo=timezone.utc)
PASSWORD = " a quiet place to grow "


@pytest.fixture(scope="module")
def hashes():
    return hash_password(PASSWORD), hash_password("a different dummy phrase")


@pytest.fixture
def setup(tmp_path, hashes):
    repo = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="成长者", email="learner@example.com")
    repo.save(user)
    repo.save_initial_password_hash(user.user_id, hashes[0])
    message = issue_email_verification(
        repo, user.user_id, "https://coach.example/verify", now=NOW
    )
    token = parse_qs(urlsplit(message.activation_url).query)["token"][0]
    assert confirm_email_verification(repo, token, now=NOW) == user.user_id
    return repo, user, hashes[1]


def login(setup, **changes):
    repo, _, dummy = setup
    fields = dict(
        email="learner@example.com", password=PASSWORD, dummy_hash=dummy, now=NOW
    )
    fields.update(changes)
    return sign_in(repo, **fields)


def test_verified_login_hashes_session_preserves_password_and_redacts_receipt(setup):
    repo, user, _ = setup
    before = repo.get_password_hash(user.user_id)
    receipt = login(setup)
    assert len(receipt.token) == 43
    assert receipt.expires_at == NOW + timedelta(hours=8)
    account = signed_in_account(repo, receipt.token, now=NOW)
    assert account.user_id == user.user_id
    assert account.name == "成长者"
    assert receipt.token not in repr(receipt) + repr(account)
    assert user.email not in repr(account)
    assert repo.get_password_hash(user.user_id) == before
    with sqlite3.connect(repo.database_path) as connection:
        stored = connection.execute("SELECT token_hash FROM login_sessions").fetchone()[
            0
        ]
    assert (
        stored
        == hashlib.sha256(b"login-session\0" + receipt.token.encode()).hexdigest()
    )
    assert receipt.token.encode() not in repo.database_path.read_bytes()
    assert PASSWORD.encode() not in repo.database_path.read_bytes()


@pytest.mark.parametrize(
    "email,password",
    [
        ("missing@example.com", PASSWORD),
        ("learner@example.com", "wrong password phrase"),
        ("learner@example.com", PASSWORD.strip()),
        ("not-an-email", PASSWORD),
        ("learner@example.com", ""),
        ("learner@example.com", "x" * 129),
        (None, PASSWORD),
    ],
)
def test_invalid_login_returns_same_no_session_result(setup, email, password):
    assert login(setup, email=email, password=password) is None


def test_email_normalization_does_not_normalize_password(setup):
    assert login(setup, email="  Learner@EXAMPLE.COM ") is not None


def test_unverified_or_legacy_account_cannot_get_session(setup):
    repo, user, _ = setup
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE user_email_verifications SET verified_at=NULL")
    assert login(setup) is None
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("DELETE FROM user_passwords")
    assert login(setup) is None
    assert repo.get_by_id(user.user_id).name == "成长者"


def test_logout_revokes_on_server_and_survives_repository_restart(setup):
    repo, _, _ = setup
    receipt = login(setup)
    sign_out(repo, receipt.token, now=NOW)
    assert signed_in_account(repo, receipt.token, now=NOW) is None
    assert (
        signed_in_account(
            SQLiteUserRepository(repo.database_path), receipt.token, now=NOW
        )
        is None
    )
    sign_out(repo, receipt.token, now=NOW)


def test_expiry_is_fixed_and_invalid_tokens_fail_closed(setup):
    repo, _, _ = setup
    receipt = login(setup)
    assert (
        signed_in_account(repo, receipt.token, now=NOW + timedelta(hours=8, seconds=-1))
        is not None
    )
    assert signed_in_account(repo, receipt.token, now=NOW + timedelta(hours=8)) is None
    assert (
        signed_in_account(repo, receipt.token, now=NOW - timedelta(seconds=1)) is None
    )
    for token in (None, "", "x", "x" * 43, "\n" * 43, "x" * 500):
        assert signed_in_account(repo, token, now=NOW) is None


def test_login_rotates_old_browser_session_without_affecting_other_browser(setup):
    repo, _, _ = setup
    first = login(setup)
    other = login(setup)
    replacement = login(setup, previous_token=first.token)
    assert replacement.token != first.token
    assert signed_in_account(repo, first.token, now=NOW) is None
    assert signed_in_account(repo, other.token, now=NOW) is not None
    assert signed_in_account(repo, replacement.token, now=NOW) is not None


def test_changing_verified_email_invalidates_existing_session(setup):
    repo, _, _ = setup
    receipt = login(setup)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE users SET email='changed@example.com'")
    assert signed_in_account(repo, receipt.token, now=NOW) is None


def test_session_insert_failure_does_not_revoke_previous_login(setup):
    repo, _, _ = setup
    first = login(setup)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_session BEFORE INSERT ON login_sessions BEGIN SELECT RAISE(ABORT, 'simulated'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        login(setup, previous_token=first.token)
    assert signed_in_account(repo, first.token, now=NOW) is not None


def test_session_cannot_be_created_for_nonexistent_user_and_expired_rows_are_cleaned(
    setup,
):
    repo, _, _ = setup
    with pytest.raises(ValueError):
        repo.save_login_session(
            "a" * 64, "missing", int(NOW.timestamp()), int(NOW.timestamp()) + 10
        )
    old = login(setup)
    fresh = login(setup, now=NOW + timedelta(hours=8))
    with sqlite3.connect(repo.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM login_sessions").fetchone()[0] == 1
        )
    assert signed_in_account(repo, old.token, now=NOW + timedelta(hours=8)) is None
    assert (
        signed_in_account(repo, fresh.token, now=NOW + timedelta(hours=8)) is not None
    )
    assert session_token_hash("bad") is None
