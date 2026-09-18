from user.service import register_user
from learning.journey_service import (
    create_learning_journey,
    start_learning_journey,
)
from learning.continuity import (
    build_learning_continuity_context,
)


def test_user_should_register_create_journey_and_start_learning(
    tmp_path,
):
    from user.sqlite_repository import (
        SQLiteUserRepository,
    )
    from learning.sqlite_journey_repository import (
        SQLiteLearningJourneyRepository,
    )
    from learning.sqlite_session_repository import (
        SQLiteLearningSessionRepository,
    )

    user_repository = SQLiteUserRepository(tmp_path / "users.db")

    journey_repository = SQLiteLearningJourneyRepository(tmp_path / "journeys.db")

    session_repository = SQLiteLearningSessionRepository(tmp_path / "sessions.db")

    user = register_user(
        repository=user_repository,
        name="张三",
        email="zhangsan@example.com",
    )

    journey = create_learning_journey(
        repository=journey_repository,
        user_repository=user_repository,
        user_id=user.user_id,
        domain="英语",
        goal="6个月达到日常交流",
    )

    session = start_learning_journey(
        repository=journey_repository,
        journey=journey,
        session_repository=session_repository,
    )

    assert user.user_id is not None

    assert journey.user_id == user.user_id
    assert journey.status == "active"

    assert session.user_id == user.user_id
    assert session.journey_id == journey.journey_id
    assert session.topic == "英语"


def test_user_should_continue_learning_across_days(
    tmp_path,
):
    from user.sqlite_repository import (
        SQLiteUserRepository,
    )
    from learning.sqlite_journey_repository import (
        SQLiteLearningJourneyRepository,
    )
    from learning.sqlite_session_repository import (
        SQLiteLearningSessionRepository,
    )

    user_db = tmp_path / "users.db"
    journey_db = tmp_path / "journeys.db"
    session_db = tmp_path / "sessions.db"

    # Day 1
    user_repository = SQLiteUserRepository(user_db)
    journey_repository = SQLiteLearningJourneyRepository(journey_db)
    session_repository = SQLiteLearningSessionRepository(session_db)

    user = register_user(
        repository=user_repository,
        name="张三",
        email="zhangsan@example.com",
    )

    journey = create_learning_journey(
        repository=journey_repository,
        user_repository=user_repository,
        user_id=user.user_id,
        domain="英语",
        goal="6个月达到日常交流",
    )

    session = start_learning_journey(
        repository=journey_repository,
        journey=journey,
        session_repository=session_repository,
    )

    session.completed = True
    session.understanding_score = 80
    session.difficulty = "听力速度较快"
    session.next_step = "练习慢速英语听力"

    session_repository.save(session)

    # Day 2: 模拟程序重新启动
    restored_session_repository = SQLiteLearningSessionRepository(session_db)

    continuity = build_learning_continuity_context(
        journey_id=journey.journey_id,
        user_id=user.user_id,
        repository=restored_session_repository,
    )

    assert continuity["has_previous_session"] is True

    assert continuity["topic"] == "英语"

    assert continuity["understanding_score"] == 80

    assert continuity["difficulty"] == "听力速度较快"

    assert continuity["next_step"] == "练习慢速英语听力"
