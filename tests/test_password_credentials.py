import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from conversation.message import ConversationMessage
from conversation.sqlite_repository import SQLiteConversationRepository
from learning.journey import LearningJourney
from learning.sqlite_journey_repository import SQLiteLearningJourneyRepository
from security.auth import initialize_user_password, verify_user_password
from security.passwords import hash_password
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


@pytest.fixture
def account(tmp_path):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="成长者", email="learner@example.com")
    repository.save(user)
    return repository, user


def test_password_persists_after_restart_without_changing_identity(account, tmp_path):
    repository, user = account
    initialize_user_password(repository, user.user_id, "a quiet place to learn")
    restored = SQLiteUserRepository(tmp_path / "users.db")
    assert verify_user_password(restored, user.user_id, "a quiet place to learn")
    assert not verify_user_password(restored, user.user_id, "a different quiet place")
    assert asdict(restored.get_by_id(user.user_id)) == asdict(user)
    assert asdict(restored.get_by_email(user.email)) == asdict(user)
    with sqlite3.connect(tmp_path / "users.db") as connection:
        stored = connection.execute(
            "SELECT password_hash FROM user_passwords"
        ).fetchone()[0]
        assert stored.startswith("$argon2id$")
        assert "a quiet place to learn" not in stored


def test_initialization_never_overwrites_existing_password(account):
    repository, user = account
    initialize_user_password(repository, user.user_id, "a quiet place to learn")
    original_hash = repository.get_password_hash(user.user_id)
    with pytest.raises(ValueError, match="password already initialized"):
        initialize_user_password(repository, user.user_id, "a different quiet place")
    assert repository.get_password_hash(user.user_id) == original_hash
    assert verify_user_password(repository, user.user_id, "a quiet place to learn")


def test_unknown_user_cannot_gain_a_credential_or_account(account):
    repository, _ = account
    assert not verify_user_password(repository, "unknown", "a quiet place to learn")
    with pytest.raises(ValueError, match="user not found"):
        initialize_user_password(repository, "unknown", "a quiet place to learn")
    assert repository.get_by_id("unknown") is None
    assert repository.get_password_hash("unknown") is None


def test_accounts_cannot_use_each_others_password(account):
    repository, first = account
    second = User(name="另一位成长者", email="another@example.com")
    repository.save(second)
    initialize_user_password(repository, first.user_id, "a quiet place to learn")
    initialize_user_password(repository, second.user_id, "a different quiet place")
    assert not verify_user_password(
        repository, first.user_id, "a different quiet place"
    )
    assert not verify_user_password(
        repository, second.user_id, "a quiet place to learn"
    )


def test_plain_text_or_invalid_password_is_never_stored(account):
    repository, user = account
    with pytest.raises(ValueError, match="Argon2id"):
        repository.save_initial_password_hash(user.user_id, "plain-text-password")
    with pytest.raises(ValueError):
        initialize_user_password(repository, user.user_id, "too-short")
    assert repository.get_password_hash(user.user_id) is None


def test_simultaneous_initializations_cannot_replace_a_credential(account):
    repository, user = account
    hashes = [
        hash_password(value)
        for value in ["a quiet place to learn", "a different quiet place"]
    ]

    def save(encoded):
        try:
            repository.save_initial_password_hash(user.user_id, encoded)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(save, hashes)) == [False, True]
    assert repository.get_password_hash(user.user_id) in hashes


def test_old_schema_keeps_identity_and_learning_records_without_default_password(
    tmp_path,
):
    user_id = "legacy-user"
    database_path = tmp_path / "users.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE users (user_id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE)"
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (user_id, "旧用户", "legacy@example.com"),
        )
    journeys = SQLiteLearningJourneyRepository(tmp_path / "journeys.db")
    journey = LearningJourney(user_id=user_id, domain="经济学", goal="理解生活里的选择")
    journeys.save(journey)
    conversations = SQLiteConversationRepository(tmp_path / "conversations.db")
    message = ConversationMessage(
        journey_id=journey.journey_id,
        user_id=user_id,
        role="user",
        content="继续上次的学习",
    )
    conversations.save(message)
    memory_path = tmp_path / "memory" / user_id / "notes.md"
    memory_path.parent.mkdir(parents=True)
    memory_path.write_text("自己的学习笔记", encoding="utf-8")
    unchanged_paths = [
        tmp_path / "journeys.db",
        tmp_path / "conversations.db",
        memory_path,
    ]
    original_data = {path: path.read_bytes() for path in unchanged_paths}

    for _ in range(2):
        repository = SQLiteUserRepository(database_path)
        assert repository.get_by_email("legacy@example.com").user_id == user_id
        assert repository.get_password_hash(user_id) is None
        assert not verify_user_password(repository, user_id, "a quiet place to learn")
    # This is an internal, trusted ownership-verified call, not a public reset path.
    initialize_user_password(repository, user_id, "a quiet place to learn")
    assert repository.get_by_id(user_id).name == "旧用户"
    assert all(path.read_bytes() == original_data[path] for path in unchanged_paths)
    assert journeys.get_by_id(journey.journey_id).user_id == user_id
    assert (
        conversations.list_by_journey(journey.journey_id, user_id)[0].content
        == message.content
    )


def test_new_credential_primitives_do_not_open_web_registration_or_login(
    account, tmp_path
):
    repository, user = account
    initialize_user_password(repository, user.user_id, "a quiet place to learn")
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
            path, data={"email": user.email, "password": "a quiet place to learn"}
        )
        # Direct registration POST now also requires the signed form context.
        assert response.status_code == (503 if path.endswith("login") else 403)
        if path.endswith("register"):
            assert "请重新打开注册页面" in response.text
            assert repository.get_by_email(user.email).user_id == user.user_id
        assert "set-cookie" not in response.headers
        assert "a quiet place to learn" not in response.text
        assert repository.get_password_hash(user.user_id) not in response.text
