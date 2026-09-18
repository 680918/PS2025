from learning.journey import LearningJourney
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)


def test_sqlite_journey_repository_should_persist_and_restore_journey(
    tmp_path,
):
    database_path = tmp_path / "learning_journeys.db"

    repository = SQLiteLearningJourneyRepository(database_path)

    journey = LearningJourney(
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    repository.save(journey)

    restored_repository = SQLiteLearningJourneyRepository(database_path)

    restored_journey = restored_repository.get_by_id(journey.journey_id)

    assert restored_journey is not None
    assert restored_journey.journey_id == journey.journey_id
    assert restored_journey.user_id == "user_001"
    assert restored_journey.domain == "英语"
    assert restored_journey.goal == "6个月达到日常交流"


def test_sqlite_journey_repository_should_list_only_user_journeys(
    tmp_path,
):
    database_path = tmp_path / "learning_journeys.db"

    repository = SQLiteLearningJourneyRepository(database_path)

    user1_journey = LearningJourney(
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    user2_journey = LearningJourney(
        user_id="user_002",
        domain="摄影",
        goal="完成旅行摄影作品",
    )

    repository.save(user1_journey)
    repository.save(user2_journey)

    journeys = repository.list_by_user("user_001")

    assert len(journeys) == 1
    assert journeys[0].journey_id == user1_journey.journey_id
    assert journeys[0].user_id == "user_001"


def test_sqlite_journey_repository_should_get_journey_only_for_owner(
    tmp_path,
):
    database_path = tmp_path / "learning_journeys.db"

    repository = SQLiteLearningJourneyRepository(database_path)

    journey = LearningJourney(
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    repository.save(journey)

    owned_journey = repository.get_by_id_for_user(
        journey_id=journey.journey_id,
        user_id="user_001",
    )

    other_user_result = repository.get_by_id_for_user(
        journey_id=journey.journey_id,
        user_id="user_002",
    )

    assert owned_journey is not None
    assert owned_journey.journey_id == journey.journey_id

    assert other_user_result is None
