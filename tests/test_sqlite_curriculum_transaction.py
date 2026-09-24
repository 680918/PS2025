import sqlite3

import pytest

from learning.curriculum import CurriculumItem, LearningCurriculum
from learning.sqlite_curriculum_repository import (
    SQLiteLearningCurriculumRepository,
)


def test_save_with_connection_should_rollback_curriculum_when_transaction_fails(
    tmp_path,
):
    database_path = tmp_path / "curriculums.db"

    repository = SQLiteLearningCurriculumRepository(database_path)

    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python函数"),
        ],
    )

    with pytest.raises(RuntimeError, match="write failed"):
        with sqlite3.connect(database_path) as connection:
            repository.save_with_connection(
                curriculum,
                connection,
            )

            raise RuntimeError("write failed")

    assert repository.get_by_journey_id("journey_001") is None
