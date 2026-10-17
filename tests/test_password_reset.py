import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from security.email_verification import (
    issue_email_verification,
    confirm_email_verification,
)
from security.login_sessions import sign_in, signed_in_account
from security.password_reset import (
    issue_password_reset,
    complete_password_reset,
    reset_available,
    reset_token_hash,
    build_password_reset_email,
    send_password_reset_email,
    send_password_changed_email,
    PasswordChangedMessage,
)
from security.passwords import hash_password, verify_password
from security.verification_mailer import SMTPSettings
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


NOW = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)
BASE = "https://coach.example.com/web/reset-password"
OLD = "a quiet place to grow today"
NEW = " 新密码：每天读书并实践2026 "


def token(message):
    return parse_qs(urlsplit(message.activation_url).query)["token"][0]


@pytest.fixture(scope="module")
def hashes():
    return hash_password(OLD), hash_password("dummy phrase for uniform work")


@pytest.fixture
def setup(tmp_path, hashes):
    repo = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="学习者", email="reader@example.com")
    repo.save(user)
    repo.save_initial_password_hash(user.user_id, hashes[0])
    confirm_email_verification(
        repo,
        token(
            issue_email_verification(
                repo, user.user_id, "https://coach.example.com/verify", now=NOW
            )
        ),
        now=NOW,
    )
    return repo, user, hashes[1]


def test_reset_once_revokes_all_own_sessions_retains_account_and_stores_only_hash(
    setup,
):
    repo, user, dummy = setup
    sessions = [
        sign_in(repo, user.email, OLD, dummy_hash=dummy, now=NOW) for _ in range(2)
    ]
    message = issue_password_reset(repo, user.email, BASE, now=NOW)
    raw = token(message)
    assert (
        len(raw) == 43 and raw not in repr(message) and user.email not in repr(message)
    )
    assert message.expires_at == NOW + timedelta(minutes=30)
    with sqlite3.connect(repo.database_path) as connection:
        stored = connection.execute(
            "SELECT token_hash FROM password_reset_tokens"
        ).fetchone()[0]
    assert stored == hashlib.sha256(b"password-reset\0" + raw.encode()).hexdigest()
    assert raw.encode() not in repo.database_path.read_bytes()
    assert reset_available(repo, raw, now=NOW)
    assert complete_password_reset(repo, raw, NEW, now=NOW) == user.email
    assert verify_password(NEW, repo.get_password_hash(user.user_id))
    assert not verify_password(NEW.strip(), repo.get_password_hash(user.user_id))
    assert not verify_password(OLD, repo.get_password_hash(user.user_id))
    assert all(
        signed_in_account(repo, item.token, now=NOW) is None for item in sessions
    )
    assert not complete_password_reset(repo, raw, OLD, now=NOW)
    assert repo.get_by_id(user.user_id).name == user.name and repo.is_email_verified(
        user.user_id
    )
    assert NEW.encode() not in repo.database_path.read_bytes()


def test_other_user_session_survives_and_own_new_password_login_works(setup, hashes):
    repo, user, dummy = setup
    other = User(name="另一个人", email="other@example.com")
    repo.save(other)
    repo.save_initial_password_hash(other.user_id, hashes[0])
    confirm_email_verification(
        repo,
        token(issue_email_verification(repo, other.user_id, BASE, now=NOW)),
        now=NOW,
    )
    session = sign_in(repo, other.email, OLD, dummy_hash=dummy, now=NOW)
    message = issue_password_reset(repo, user.email, BASE, now=NOW)
    assert complete_password_reset(repo, token(message), NEW, now=NOW)
    assert signed_in_account(repo, session.token, now=NOW)
    assert sign_in(repo, user.email, OLD, dummy_hash=dummy, now=NOW) is None
    assert sign_in(repo, user.email, NEW, dummy_hash=dummy, now=NOW)


def test_unknown_unverified_legacy_and_email_changed_cannot_reset(setup):
    repo, user, _ = setup
    assert issue_password_reset(repo, "missing@example.com", BASE, now=NOW) is None
    message = issue_password_reset(repo, user.email, BASE, now=NOW)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE users SET email='changed@example.com'")
    assert not reset_available(repo, token(message), now=NOW)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE users SET email=?", (user.email,))
        connection.execute("UPDATE user_email_verifications SET verified_at=NULL")
    assert (
        issue_password_reset(repo, user.email, BASE, now=NOW + timedelta(seconds=61))
        is None
    )
    assert not complete_password_reset(repo, token(message), NEW, now=NOW)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE user_email_verifications SET verified_at=1")
        connection.execute("DELETE FROM user_passwords")
    assert (
        issue_password_reset(repo, user.email, BASE, now=NOW + timedelta(seconds=61))
        is None
    )


def test_cooldown_restart_new_link_supersedes_old_and_expiry_is_exact(setup):
    repo, user, _ = setup
    first = issue_password_reset(repo, user.email, BASE, now=NOW)
    restarted = SQLiteUserRepository(repo.database_path)
    assert (
        issue_password_reset(
            restarted, user.email, BASE, now=NOW + timedelta(seconds=59)
        )
        is None
    )
    second = issue_password_reset(
        restarted, user.email, BASE, now=NOW + timedelta(seconds=60)
    )
    assert not reset_available(repo, token(first), now=NOW + timedelta(seconds=60))
    assert reset_available(repo, token(second), now=NOW + timedelta(seconds=1859))
    assert not reset_available(repo, token(second), now=NOW + timedelta(seconds=1860))
    assert not reset_available(repo, token(second), now=NOW)


def test_concurrent_consumption_exactly_once_and_rollback_on_failure(setup):
    repo, user, _ = setup
    raw = token(issue_password_reset(repo, user.email, BASE, now=NOW))
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda _: complete_password_reset(repo, raw, NEW, now=NOW), range(2)
            )
        )
    assert sum(bool(item) for item in results) == 1


def test_transaction_rolls_back_password_token_and_sessions_on_failed_revoke(setup):
    repo, user, dummy = setup
    session = sign_in(repo, user.email, OLD, dummy_hash=dummy, now=NOW)
    raw = token(issue_password_reset(repo, user.email, BASE, now=NOW))
    before = repo.get_password_hash(user.user_id)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_reset BEFORE UPDATE ON login_sessions BEGIN SELECT RAISE(ABORT,'test failure'); END"
        )
    with pytest.raises(sqlite3.Error):
        complete_password_reset(repo, raw, NEW, now=NOW)
    assert repo.get_password_hash(user.user_id) == before
    assert reset_available(repo, raw, now=NOW) and signed_in_account(
        repo, session.token, now=NOW
    )


def test_old_password_login_racing_with_reset_never_creates_session(setup, monkeypatch):
    repo, user, dummy = setup
    raw = token(issue_password_reset(repo, user.email, BASE, now=NOW))
    original = repo.save_login_session

    def race(*args, **kwargs):
        assert complete_password_reset(repo, raw, NEW, now=NOW)
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "save_login_session", race)
    assert sign_in(repo, user.email, OLD, dummy_hash=dummy, now=NOW) is None
    with sqlite3.connect(repo.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM login_sessions").fetchone()[0] == 0
        )


def test_final_expiry_is_rechecked_after_password_hashing(setup, monkeypatch):
    import security.password_reset as reset

    repo, user, _ = setup
    raw = token(issue_password_reset(repo, user.email, BASE, now=NOW))
    times = iter([int(NOW.timestamp()), int(NOW.timestamp()) + 1800])
    monkeypatch.setattr(reset, "_timestamp", lambda now: next(times))
    assert not complete_password_reset(repo, raw, NEW)


@pytest.mark.parametrize("raw", [None, "", "x", "x" * 44, "中" * 43, "\n" * 43])
def test_invalid_tokens_never_reach_database(setup, raw):
    repo, _, _ = setup
    assert reset_token_hash(raw) is None
    assert not complete_password_reset(repo, raw, NEW, now=NOW)


def test_registration_token_cannot_reset_password_and_invalid_password_does_not_consume(
    setup,
):
    repo, user, _ = setup
    raw = token(issue_password_reset(repo, user.email, BASE, now=NOW))
    for password in ("short", " " * 20, "x" * 129):
        with pytest.raises(ValueError):
            complete_password_reset(repo, raw, password, now=NOW)
        assert reset_available(repo, raw, now=NOW)
    assert not complete_password_reset(repo, "z" * 43, NEW, now=NOW)


def test_reset_email_and_notification_have_no_password_and_reuse_tls_transport(
    setup, monkeypatch
):
    import security.password_reset as reset

    repo, user, _ = setup
    message = issue_password_reset(repo, user.email, BASE, now=NOW)
    mail = build_password_reset_email(message, "sender@163.com", now=NOW)
    assert mail["Subject"] == "重新设置你的知行密码"
    assert token(message) in mail.get_body(preferencelist=("plain",)).get_content()
    assert "设置新密码" in mail.get_body(preferencelist=("html",)).get_content()
    captured = []
    monkeypatch.setattr(
        reset, "_send_mail_message", lambda *args: captured.append(args)
    )
    settings = SMTPSettings("sender@163.com", "fake-code")
    send_password_reset_email(message, settings, now=NOW)
    send_password_changed_email(PasswordChangedMessage(user.email), settings, now=NOW)
    assert len(captured) == 2
    for item in captured:
        assert item[1] == user.email
        assert OLD not in item[0].as_string() and NEW not in item[0].as_string()
    notification = captured[1][0].get_content()
    assert "已失效" in notification and token(message) not in notification
    with pytest.raises(ValueError):
        build_password_reset_email(
            message, "sender@163.com", now=NOW + timedelta(minutes=30)
        )
