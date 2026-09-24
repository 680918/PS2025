import sqlite3

import pytest

from learning.curriculum import CurriculumItem, LearningCurriculum
from learning.journey import LearningJourney
from learning.sqlite_curriculum_repository import (
    SQLiteLearningCurriculumRepository,
)
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)


def test_journey_and_curriculum_should_rollback_together_when_write_fails(
    tmp_path,
):
    database_path = tmp_path / "learning.db"

    journey_repository = SQLiteLearningJourneyRepository(database_path)
    curriculum_repository = SQLiteLearningCurriculumRepository(database_path)

    journey = LearningJourney(
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
    )

    curriculum = LearningCurriculum(
        journey_id=journey.journey_id,
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=1, topic="Python函数"),
        ],
    )

    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(database_path) as connection:
            journey_repository.save_with_connection(journey, connection)
            curriculum_repository.save_with_connection(curriculum, connection)

    assert journey_repository.get_by_id(journey.journey_id) is None
    assert curriculum_repository.get_by_journey_id(journey.journey_id) is None
