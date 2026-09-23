from learning.curriculum import CurriculumItem, LearningCurriculum
from learning.sqlite_curriculum_repository import (
    SQLiteLearningCurriculumRepository,
)


def test_sqlite_curriculum_repository_should_persist_and_restore_curriculum(
    tmp_path,
):
    database_path = tmp_path / "learning_curriculums.db"

    repository = SQLiteLearningCurriculumRepository(database_path)

    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
            CurriculumItem(position=3, topic="Python循环"),
        ],
    )

    repository.save(curriculum)

    restored_repository = SQLiteLearningCurriculumRepository(database_path)

    restored_curriculum = restored_repository.get_by_journey_id("journey_001")

    assert restored_curriculum is not None
    assert restored_curriculum.journey_id == "journey_001"

    assert [(item.position, item.topic) for item in restored_curriculum.items] == [
        (1, "Python变量"),
        (2, "Python条件判断"),
        (3, "Python循环"),
    ]


def test_sqlite_curriculum_repository_should_replace_existing_items(
    tmp_path,
):
    database_path = tmp_path / "learning_curriculums.db"

    repository = SQLiteLearningCurriculumRepository(database_path)

    original_curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
        ],
    )

    repository.save(original_curriculum)

    updated_curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python函数"),
            CurriculumItem(position=3, topic="Python异常处理"),
        ],
    )

    repository.save(updated_curriculum)

    restored_repository = SQLiteLearningCurriculumRepository(database_path)

    restored = restored_repository.get_by_journey_id("journey_001")

    assert restored is not None

    assert [(item.position, item.topic) for item in restored.items] == [
        (1, "Python变量"),
        (2, "Python函数"),
        (3, "Python异常处理"),
    ]


def test_sqlite_curriculum_repository_should_preserve_empty_curriculum(
    tmp_path,
):
    database_path = tmp_path / "learning_curriculums.db"

    repository = SQLiteLearningCurriculumRepository(database_path)

    assert repository.get_by_journey_id("journey_001") is None

    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[],
    )

    repository.save(curriculum)

    restored_repository = SQLiteLearningCurriculumRepository(database_path)

    restored = restored_repository.get_by_journey_id("journey_001")

    assert restored is not None
    assert restored.journey_id == "journey_001"
    assert restored.items == []


def test_sqlite_curriculum_repository_should_isolate_journey_items(
    tmp_path,
):
    database_path = tmp_path / "learning_curriculums.db"

    repository = SQLiteLearningCurriculumRepository(database_path)

    repository.save(
        LearningCurriculum(
            journey_id="journey_001",
            items=[
                CurriculumItem(position=1, topic="Python变量"),
                CurriculumItem(position=2, topic="Python函数"),
            ],
        )
    )

    repository.save(
        LearningCurriculum(
            journey_id="journey_002",
            items=[
                CurriculumItem(position=1, topic="英语听力"),
                CurriculumItem(position=2, topic="英语口语"),
            ],
        )
    )

    restored_repository = SQLiteLearningCurriculumRepository(database_path)

    python_curriculum = restored_repository.get_by_journey_id("journey_001")
    english_curriculum = restored_repository.get_by_journey_id("journey_002")

    assert python_curriculum is not None
    assert english_curriculum is not None

    assert [item.topic for item in python_curriculum.items] == [
        "Python变量",
        "Python函数",
    ]

    assert [item.topic for item in english_curriculum.items] == [
        "英语听力",
        "英语口语",
    ]
