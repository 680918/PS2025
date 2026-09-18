from learning.session import LearningSession
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)
from datetime import timedelta


def test_sqlite_repository_should_persist_and_restore_session(
    tmp_path,
):
    database_path = tmp_path / "learning_sessions.db"

    repository = SQLiteLearningSessionRepository(database_path)

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        completed=True,
        understanding_score=85,
        difficulty="参数校验还不熟",
        next_step="继续练习 Tool Schema",
    )

    repository.save(session)

    restored_repository = SQLiteLearningSessionRepository(database_path)

    restored_session = restored_repository.get_latest_by_journey("journey_001")

    assert restored_session is not None
    assert restored_session.session_id == session.session_id
    assert restored_session.topic == "Tool Calling"
    assert restored_session.next_step == "继续练习 Tool Schema"


def test_sqlite_repository_should_return_none_when_no_session_exists(
    tmp_path,
):
    database_path = tmp_path / "learning_sessions.db"

    repository = SQLiteLearningSessionRepository(database_path)

    restored_session = repository.get_latest_by_journey("journey_missing")

    assert restored_session is None


def test_sqlite_repository_should_return_latest_session(
    tmp_path,
):
    database_path = tmp_path / "learning_sessions.db"

    repository = SQLiteLearningSessionRepository(database_path)

    first_session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Memory",
        next_step="继续学习 Tool Calling",
    )

    second_session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        next_step="继续练习 Tool Schema",
        created_at=(first_session.created_at + timedelta(hours=1)),
        updated_at=(first_session.updated_at + timedelta(hours=1)),
    )

    repository.save(first_session)
    repository.save(second_session)

    latest_session = repository.get_latest_by_journey("journey_001")

    assert latest_session is not None
    assert latest_session.session_id == second_session.session_id
    assert latest_session.topic == "Tool Calling"


def test_sqlite_session_repository_should_return_latest_session_only_for_owner(
    tmp_path,
):
    database_path = tmp_path / "learning_sessions.db"

    repository = SQLiteLearningSessionRepository(database_path)

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        next_step="继续练习 Tool Schema",
    )

    repository.save(session)

    owned_session = repository.get_latest_by_journey_for_user(
        journey_id="journey_001",
        user_id="user_001",
    )

    other_user_result = repository.get_latest_by_journey_for_user(
        journey_id="journey_001",
        user_id="user_002",
    )

    assert owned_session is not None
    assert owned_session.session_id == session.session_id

    assert other_user_result is None
