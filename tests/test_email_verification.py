import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from conversation.message import ConversationMessage
from conversation.sqlite_repository import SQLiteConversationRepository
from learning.journey import LearningJourney
from learning.sqlite_journey_repository import SQLiteLearningJourneyRepository
from security.auth import verify_user_password
from security.email_verification import (
    confirm_email_verification,
    issue_email_verification,
)
from security.passwords import hash_password
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


NOW = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
ACTIVATION_URL = "https://coach.example.com/web/verify-email"


def token_from(message):
    return parse_qs(urlsplit(message.activation_url).query)["token"][0]


@pytest.fixture
def account(tmp_path):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="成长者", email="learner@example.com")
    repository.save(user)
    return repository, user


def test_simulated_mail_verifies_only_after_confirmation(account, capsys):
    repository, user = account
    outbox = [
        issue_email_verification(repository, user.user_id, ACTIVATION_URL, now=NOW)
    ]
    message = outbox[0]
    token = token_from(message)
    assert message.recipient == user.email
    assert message.expires_at == NOW + timedelta(hours=1)
    assert not repository.is_email_verified(user.user_id)
    assert repository.get_password_hash(user.user_id) is None
    with sqlite3.connect(repository.database_path) as connection:
        stored_hash = connection.execute(
            "SELECT token_hash FROM user_email_verifications"
        ).fetchone()[0]
    assert stored_hash == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert token not in stored_hash
    assert token not in repr(message)
    assert user.email not in repr(message)
    assert confirm_email_verification(repository, token, now=NOW) == user.user_id
    assert repository.is_email_verified(user.user_id)
    assert asdict(repository.get_by_id(user.user_id)) == asdict(user)
    assert repository.get_password_hash(user.user_id) is None
    with sqlite3.connect(repository.database_path) as connection:
        assert (
            connection.execute(
                "SELECT token_hash FROM user_email_verifications"
            ).fetchone()[0]
            is None
        )
    assert capsys.readouterr().out == ""


def test_used_link_cannot_be_used_or_issued_again_for_verified_email(account):
    repository, user = account
    message = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    assert (
        confirm_email_verification(repository, token_from(message), now=NOW)
        == user.user_id
    )
    assert confirm_email_verification(repository, token_from(message), now=NOW) is None
    with pytest.raises(ValueError, match="email verification unavailable"):
        issue_email_verification(
            repository, user.user_id, ACTIVATION_URL, now=NOW + timedelta(hours=2)
        )
    assert repository.is_email_verified(user.user_id)


@pytest.mark.parametrize(
    "seconds, valid", [(-1, False), (3599, True), (3600, False), (3601, False)]
)
def test_expiration_and_issue_time_boundaries(account, seconds, valid):
    repository, user = account
    message = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    result = confirm_email_verification(
        repository, token_from(message), now=NOW + timedelta(seconds=seconds)
    )
    assert result == (user.user_id if valid else None)
    assert repository.is_email_verified(user.user_id) is valid


def test_resending_replaces_old_link_at_cooldown_boundary(account):
    repository, user = account
    first = issue_email_verification(repository, user.user_id, ACTIVATION_URL, now=NOW)
    later = NOW + timedelta(seconds=60)
    second = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=later
    )
    assert token_from(first) != token_from(second)
    assert confirm_email_verification(repository, token_from(first), now=later) is None
    assert (
        confirm_email_verification(repository, token_from(second), now=later)
        == user.user_id
    )


@pytest.mark.parametrize("seconds", [0, 59])
def test_resend_too_soon_preserves_original_link(account, seconds):
    repository, user = account
    original = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    with pytest.raises(ValueError, match="email verification unavailable"):
        issue_email_verification(
            repository,
            user.user_id,
            ACTIVATION_URL,
            now=NOW + timedelta(seconds=seconds),
        )
    assert (
        confirm_email_verification(repository, token_from(original), now=NOW)
        == user.user_id
    )


def test_pending_link_and_verified_status_survive_restart(account):
    repository, user = account
    message = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    restored = SQLiteUserRepository(repository.database_path)
    assert (
        confirm_email_verification(restored, token_from(message), now=NOW)
        == user.user_id
    )
    restored_again = SQLiteUserRepository(repository.database_path)
    assert restored_again.is_email_verified(user.user_id)
    assert (
        confirm_email_verification(restored_again, token_from(message), now=NOW) is None
    )


def test_accounts_have_distinct_tokens_and_only_own_email_is_verified(account):
    repository, first = account
    second = User(name="另一位成长者", email="another@example.com")
    repository.save(second)
    first_message = issue_email_verification(
        repository, first.user_id, ACTIVATION_URL, now=NOW
    )
    second_message = issue_email_verification(
        repository, second.user_id, ACTIVATION_URL, now=NOW
    )
    assert first_message.recipient == first.email
    assert second_message.recipient == second.email
    assert token_from(first_message) != token_from(second_message)
    assert (
        confirm_email_verification(repository, token_from(first_message), now=NOW)
        == first.user_id
    )
    assert not repository.is_email_verified(second.user_id)


def test_unknown_user_or_random_token_never_creates_or_verifies_account(account):
    repository, _ = account
    with pytest.raises(ValueError, match="email verification unavailable"):
        issue_email_verification(repository, "unknown", ACTIVATION_URL, now=NOW)
    assert confirm_email_verification(repository, "a" * 43, now=NOW) is None
    assert not repository.is_email_verified("unknown")
    assert repository.get_by_id("unknown") is None
    with sqlite3.connect(repository.database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM user_email_verifications"
            ).fetchone()[0]
            == 0
        )


def test_stored_hash_is_not_accepted_as_a_bearer_token(account):
    repository, user = account
    message = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    digest = hashlib.sha256(token_from(message).encode("ascii")).hexdigest()
    assert confirm_email_verification(repository, digest, now=NOW) is None
    assert not repository.is_email_verified(user.user_id)


@pytest.mark.parametrize("confirm_first", [False, True])
def test_changed_email_never_inherits_old_link_or_verified_status(
    account, confirm_first
):
    repository, user = account
    original = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    if confirm_first:
        assert (
            confirm_email_verification(repository, token_from(original), now=NOW)
            == user.user_id
        )
    # Simulate a future email-change flow; no public email-change endpoint is added.
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE users SET email = ? WHERE user_id = ?",
            ("new@example.com", user.user_id),
        )
    assert not repository.is_email_verified(user.user_id)
    assert confirm_email_verification(repository, token_from(original), now=NOW) is None
    later = NOW + timedelta(seconds=60)
    replacement = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=later
    )
    assert replacement.recipient == "new@example.com"
    assert (
        confirm_email_verification(repository, token_from(replacement), now=later)
        == user.user_id
    )
    assert repository.is_email_verified(user.user_id)


def test_concurrent_confirmation_has_exactly_one_success(account):
    repository, user = account
    message = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: confirm_email_verification(
                    repository, token_from(message), now=NOW
                ),
                range(2),
            )
        )
    assert results.count(user.user_id) == 1
    assert results.count(None) == 1


def test_concurrent_resends_do_not_issue_two_active_links(account):
    repository, user = account
    original = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    later = NOW + timedelta(seconds=60)

    def resend(_):
        try:
            return issue_email_verification(
                repository, user.user_id, ACTIVATION_URL, now=later
            )
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        messages = [
            message for message in executor.map(resend, range(2)) if message is not None
        ]
    assert len(messages) == 1
    assert (
        confirm_email_verification(repository, token_from(original), now=later) is None
    )
    assert (
        confirm_email_verification(repository, token_from(messages[0]), now=later)
        == user.user_id
    )


def test_old_tables_passwords_and_learning_files_survive_initialization(tmp_path):
    database_path = tmp_path / "users.db"
    existing_hash = hash_password("a quiet place to learn")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE users (user_id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE)"
        )
        connection.execute(
            "INSERT INTO users VALUES ('legacy-user', '旧用户', 'legacy@example.com')"
        )
        connection.execute(
            "CREATE TABLE user_passwords (user_id TEXT PRIMARY KEY NOT NULL, password_hash TEXT NOT NULL, FOREIGN KEY (user_id) REFERENCES users (user_id))"
        )
        connection.execute(
            "INSERT INTO user_passwords VALUES (?, ?)", ("legacy-user", existing_hash)
        )
    journeys = SQLiteLearningJourneyRepository(tmp_path / "journeys.db")
    journey = LearningJourney(
        user_id="legacy-user", domain="经济学", goal="理解生活中的选择"
    )
    journeys.save(journey)
    conversations = SQLiteConversationRepository(tmp_path / "conversations.db")
    conversations.save(
        ConversationMessage(
            journey_id=journey.journey_id,
            user_id="legacy-user",
            role="user",
            content="继续学习",
        )
    )
    memory_path = tmp_path / "notes.md"
    memory_path.write_text("自己的笔记", encoding="utf-8")
    paths = [tmp_path / "journeys.db", tmp_path / "conversations.db", memory_path]
    baseline = {path: path.read_bytes() for path in paths}

    for _ in range(2):
        repository = SQLiteUserRepository(database_path)
        assert not repository.is_email_verified("legacy-user")
        assert verify_user_password(repository, "legacy-user", "a quiet place to learn")
    message = issue_email_verification(
        repository, "legacy-user", ACTIVATION_URL, now=NOW
    )
    assert (
        confirm_email_verification(repository, token_from(message), now=NOW)
        == "legacy-user"
    )
    assert repository.get_password_hash("legacy-user") == existing_hash
    assert repository.get_by_email("legacy@example.com").user_id == "legacy-user"
    assert all(path.read_bytes() == baseline[path] for path in paths)


def test_verification_does_not_enable_web_login_or_registration(account, tmp_path):
    repository, user = account
    message = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=NOW
    )
    assert (
        confirm_email_verification(repository, token_from(message), now=NOW)
        == user.user_id
    )
    client = TestClient(
        create_app(
            database_dir=tmp_path,
            curriculum_generator=None,
            completion_commentary_generator=None,
            learning_feedback_extractor=None,
        )
    )
    for path in ["/web/auth/login", "/web/auth/register"]:
        response = client.post(
            path, data={"email": user.email, "token": token_from(message)}
        )
        assert response.status_code == (503 if path.endswith("login") else 400)
        assert "set-cookie" not in response.headers
        assert token_from(message) not in response.text


def test_default_utc_clock_works_without_test_override(account):
    repository, user = account
    message = issue_email_verification(repository, user.user_id, ACTIVATION_URL)
    assert message.expires_at.tzinfo == timezone.utc
    assert confirm_email_verification(repository, token_from(message)) == user.user_id


def test_china_and_utc_clocks_at_same_instant_have_same_result(account):
    repository, user = account
    china_time = NOW.astimezone(timezone(timedelta(hours=8)))
    message = issue_email_verification(
        repository, user.user_id, ACTIVATION_URL, now=china_time
    )
    assert message.expires_at == NOW + timedelta(hours=1)
    assert (
        confirm_email_verification(repository, token_from(message), now=NOW)
        == user.user_id
    )
