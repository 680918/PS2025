import sqlite3

import pytest

from learning.curriculum import CurriculumItem, LearningCurriculum
from learning.journey import LearningJourney
from learning.journey_curriculum_unit_of_work import (
    SQLiteJourneyCurriculumUnitOfWork,
)
from learning.sqlite_curriculum_repository import (
    SQLiteLearningCurriculumRepository,
)
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)


def test_unit_of_work_should_rollback_both_writes_when_curriculum_fails(
    tmp_path,
):
    database_path = tmp_path / "learning.db"

    journey_repository = SQLiteLearningJourneyRepository(database_path)
    curriculum_repository = SQLiteLearningCurriculumRepository(database_path)

    unit_of_work = SQLiteJourneyCurriculumUnitOfWork(
        database_path=database_path,
        journey_repository=journey_repository,
        curriculum_repository=curriculum_repository,
    )

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
        unit_of_work.save(journey, curriculum)

    assert journey_repository.get_by_id(journey.journey_id) is None
    assert curriculum_repository.get_by_journey_id(journey.journey_id) is None


def test_unit_of_work_should_commit_journey_and_curriculum_together(
    tmp_path,
):
    database_path = tmp_path / "learning.db"

    journey_repository = SQLiteLearningJourneyRepository(database_path)
    curriculum_repository = SQLiteLearningCurriculumRepository(database_path)

    unit_of_work = SQLiteJourneyCurriculumUnitOfWork(
        database_path=database_path,
        journey_repository=journey_repository,
        curriculum_repository=curriculum_repository,
    )

    journey = LearningJourney(
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
    )

    curriculum = LearningCurriculum(
        journey_id=journey.journey_id,
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python函数"),
        ],
    )

    unit_of_work.save(journey, curriculum)

    saved_journey = journey_repository.get_by_id(journey.journey_id)
    saved_curriculum = curriculum_repository.get_by_journey_id(journey.journey_id)

    assert saved_journey is not None
    assert saved_journey.journey_id == journey.journey_id

    assert saved_curriculum is not None
    assert [(item.position, item.topic) for item in saved_curriculum.items] == [
        (1, "Python变量"),
        (2, "Python函数"),
    ]


def test_unit_of_work_should_save_to_existing_separate_database_files(
    tmp_path,
):
    journey_database_path = tmp_path / "journeys.db"
    curriculum_database_path = tmp_path / "curriculums.db"

    journey_repository = SQLiteLearningJourneyRepository(journey_database_path)
    curriculum_repository = SQLiteLearningCurriculumRepository(curriculum_database_path)

    unit_of_work = SQLiteJourneyCurriculumUnitOfWork(
        database_path=journey_database_path,
        journey_repository=journey_repository,
        curriculum_repository=curriculum_repository,
    )

    journey = LearningJourney(
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
    )

    curriculum = LearningCurriculum(
        journey_id=journey.journey_id,
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python函数"),
        ],
    )

    unit_of_work.save(journey, curriculum)

    assert journey_repository.get_by_id(journey.journey_id) is not None

    saved_curriculum = curriculum_repository.get_by_journey_id(journey.journey_id)
    assert saved_curriculum is not None
    assert [item.topic for item in saved_curriculum.items] == [
        "Python变量",
        "Python函数",
    ]


def test_unit_of_work_should_rollback_separate_database_files_when_curriculum_fails(
    tmp_path,
):
    journey_database_path = tmp_path / "journeys.db"
    curriculum_database_path = tmp_path / "curriculums.db"

    journey_repository = SQLiteLearningJourneyRepository(journey_database_path)
    curriculum_repository = SQLiteLearningCurriculumRepository(curriculum_database_path)

    unit_of_work = SQLiteJourneyCurriculumUnitOfWork(
        database_path=journey_database_path,
        journey_repository=journey_repository,
        curriculum_repository=curriculum_repository,
    )

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
        unit_of_work.save(journey, curriculum)

    assert journey_repository.get_by_id(journey.journey_id) is None
    assert curriculum_repository.get_by_journey_id(journey.journey_id) is None


@pytest.mark.parametrize(
    "wal_database",
    ["journeys", "curriculums"],
)
def test_unit_of_work_should_reject_wal_before_cross_database_writes(
    tmp_path,
    wal_database,
):
    journey_database_path = tmp_path / "journeys.db"
    curriculum_database_path = tmp_path / "curriculums.db"

    journey_repository = SQLiteLearningJourneyRepository(journey_database_path)
    curriculum_repository = SQLiteLearningCurriculumRepository(curriculum_database_path)

    wal_path = (
        journey_database_path
        if wal_database == "journeys"
        else curriculum_database_path
    )

    with sqlite3.connect(wal_path) as connection:
        mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]

    assert mode.lower() == "wal"

    unit_of_work = SQLiteJourneyCurriculumUnitOfWork(
        database_path=journey_database_path,
        journey_repository=journey_repository,
        curriculum_repository=curriculum_repository,
    )

    journey = LearningJourney(
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
    )

    curriculum = LearningCurriculum(
        journey_id=journey.journey_id,
        items=[
            CurriculumItem(position=1, topic="Python变量"),
        ],
    )

    with pytest.raises(RuntimeError, match="WAL"):
        unit_of_work.save(journey, curriculum)

    assert journey_repository.get_by_id(journey.journey_id) is None
    assert curriculum_repository.get_by_journey_id(journey.journey_id) is None


def test_unit_of_work_should_allow_wal_for_single_database(
    tmp_path,
):
    database_path = tmp_path / "learning.db"

    journey_repository = SQLiteLearningJourneyRepository(database_path)
    curriculum_repository = SQLiteLearningCurriculumRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]

    assert mode.lower() == "wal"

    unit_of_work = SQLiteJourneyCurriculumUnitOfWork(
        database_path=database_path,
        journey_repository=journey_repository,
        curriculum_repository=curriculum_repository,
    )

    journey = LearningJourney(
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
    )

    curriculum = LearningCurriculum(
        journey_id=journey.journey_id,
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python函数"),
        ],
    )

    unit_of_work.save(journey, curriculum)

    assert journey_repository.get_by_id(journey.journey_id) is not None

    saved_curriculum = curriculum_repository.get_by_journey_id(journey.journey_id)

    assert saved_curriculum is not None
    assert [item.topic for item in saved_curriculum.items] == [
        "Python变量",
        "Python函数",
    ]
