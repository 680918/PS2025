import sqlite3

import pytest

from learning.journey import LearningJourney
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)


def test_save_with_connection_should_rollback_journey_when_transaction_fails(
    tmp_path,
):
    database_path = tmp_path / "journeys.db"

    repository = SQLiteLearningJourneyRepository(database_path)

    journey = LearningJourney(
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
    )

    with pytest.raises(RuntimeError, match="write failed"):
        with sqlite3.connect(database_path) as connection:
            repository.save_with_connection(
                journey,
                connection,
            )

            raise RuntimeError("write failed")

    assert repository.get_by_id(journey.journey_id) is None
