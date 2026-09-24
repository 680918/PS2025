import pytest

from learning.journey_service import (
    create_learning_journey,
    start_learning_journey,
    complete_learning_journey,
)


def test_create_learning_journey_should_create_and_save_journey():
    class FakeRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    repository = FakeRepository()

    journey = create_learning_journey(
        repository=repository,
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    assert journey.user_id == "user_001"
    assert journey.domain == "英语"
    assert journey.goal == "6个月达到日常交流"

    assert len(repository.saved_journeys) == 1

    assert repository.saved_journeys[0] is journey


def test_create_journey_should_initialize_explicit_curriculum():
    class FakeJourneyRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    class FakeCurriculumRepository:
        def __init__(self):
            self.saved_curriculums = []

        def save(self, curriculum):
            self.saved_curriculums.append(curriculum)

    journey_repository = FakeJourneyRepository()
    curriculum_repository = FakeCurriculumRepository()

    journey = create_learning_journey(
        repository=journey_repository,
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
        curriculum_topics=[
            "Python变量",
            "Python条件判断",
            "Python循环",
        ],
        curriculum_repository=curriculum_repository,
    )

    assert len(journey_repository.saved_journeys) == 1
    assert journey_repository.saved_journeys[0] is journey

    assert len(curriculum_repository.saved_curriculums) == 1

    curriculum = curriculum_repository.saved_curriculums[0]

    assert curriculum.journey_id == journey.journey_id

    assert [(item.position, item.topic) for item in curriculum.items] == [
        (1, "Python变量"),
        (2, "Python条件判断"),
        (3, "Python循环"),
    ]


def test_create_journey_should_reject_curriculum_without_repository():
    class FakeJourneyRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    journey_repository = FakeJourneyRepository()

    with pytest.raises(
        ValueError,
        match="curriculum repository is required",
    ):
        create_learning_journey(
            repository=journey_repository,
            user_id="user_001",
            domain="Python",
            goal="掌握 Python 编程",
            curriculum_topics=[
                "Python变量",
                "Python函数",
            ],
        )

    assert journey_repository.saved_journeys == []


def test_create_journey_without_curriculum_topics_should_not_save_curriculum():
    class FakeJourneyRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    class FakeCurriculumRepository:
        def __init__(self):
            self.saved_curriculums = []

        def save(self, curriculum):
            self.saved_curriculums.append(curriculum)

    journey_repository = FakeJourneyRepository()
    curriculum_repository = FakeCurriculumRepository()

    journey = create_learning_journey(
        repository=journey_repository,
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
        curriculum_repository=curriculum_repository,
    )

    assert journey_repository.saved_journeys == [journey]
    assert curriculum_repository.saved_curriculums == []


def test_create_journey_should_reject_curriculum_topics_that_are_not_a_list():
    class FakeJourneyRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    class FakeCurriculumRepository:
        def __init__(self):
            self.saved_curriculums = []

        def save(self, curriculum):
            self.saved_curriculums.append(curriculum)

    journey_repository = FakeJourneyRepository()
    curriculum_repository = FakeCurriculumRepository()

    with pytest.raises(
        ValueError,
        match="curriculum_topics must be a list of strings",
    ):
        create_learning_journey(
            repository=journey_repository,
            user_id="user_001",
            domain="Python",
            goal="掌握 Python 编程",
            curriculum_topics="Python变量",
            curriculum_repository=curriculum_repository,
        )

    assert journey_repository.saved_journeys == []
    assert curriculum_repository.saved_curriculums == []


def test_create_learning_journey_should_reject_unknown_user():
    class FakeJourneyRepository:
        def save(self, journey):
            raise AssertionError("journey should not be saved")

    class FakeUserRepository:
        def get_by_id(self, user_id):
            assert user_id == "user_999"
            return None

    with pytest.raises(
        ValueError,
        match="user not found",
    ):
        create_learning_journey(
            repository=FakeJourneyRepository(),
            user_repository=FakeUserRepository(),
            user_id="user_999",
            domain="英语",
            goal="6个月达到日常交流",
        )


def test_create_learning_journey_should_allow_existing_user():
    class FakeJourneyRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    class FakeUser:
        user_id = "user_001"

    class FakeUserRepository:
        def get_by_id(self, user_id):
            assert user_id == "user_001"
            return FakeUser()

    journey_repository = FakeJourneyRepository()

    journey = create_learning_journey(
        repository=journey_repository,
        user_repository=FakeUserRepository(),
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    assert journey.user_id == "user_001"
    assert journey.domain == "英语"
    assert journey.goal == "6个月达到日常交流"

    assert len(journey_repository.saved_journeys) == 1


def test_create_learning_journey_should_reject_empty_domain():
    class FakeJourneyRepository:
        def save(self, journey):
            raise AssertionError("invalid journey should not be saved")

    with pytest.raises(
        ValueError,
        match="domain is required",
    ):
        create_learning_journey(
            repository=FakeJourneyRepository(),
            user_id="user_001",
            domain="   ",
            goal="6个月达到日常交流",
        )


def test_create_learning_journey_should_reject_empty_goal():
    class FakeJourneyRepository:
        def save(self, journey):
            raise AssertionError("invalid journey should not be saved")

    with pytest.raises(
        ValueError,
        match="goal is required",
    ):
        create_learning_journey(
            repository=FakeJourneyRepository(),
            user_id="user_001",
            domain="英语",
            goal="   ",
        )


def test_start_learning_journey_should_activate_journey():
    class FakeRepository:
        def __init__(self):
            self.saved = []

        def save(self, journey):
            self.saved.append(journey)

    journey_repository = FakeRepository()

    journey = create_learning_journey(
        repository=journey_repository,
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    activated_journey = start_learning_journey(
        repository=journey_repository,
        journey=journey,
    )

    assert activated_journey.status == "active"

    assert journey_repository.saved[-1] == activated_journey


def test_start_learning_journey_should_create_real_learning_session():
    class FakeJourneyRepository:
        def save(self, journey):
            pass

    class FakeSessionRepository:
        def __init__(self):
            self.saved_sessions = []

        def save(self, session):
            self.saved_sessions.append(session)

    journey_repository = FakeJourneyRepository()
    session_repository = FakeSessionRepository()

    journey = create_learning_journey(
        repository=journey_repository,
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    session = start_learning_journey(
        repository=journey_repository,
        journey=journey,
        session_repository=session_repository,
    )

    assert session.journey_id == journey.journey_id
    assert session.user_id == journey.user_id
    assert session.topic == journey.domain

    assert len(session_repository.saved_sessions) == 1

    assert session_repository.saved_sessions[0] is session


def test_start_learning_journey_should_not_create_duplicate_first_session():
    class FakeJourneyRepository:
        def save(self, journey):
            pass

    class FakeSessionRepository:
        def __init__(self):
            self.saved_sessions = []

        def save(self, session):
            self.saved_sessions.append(session)

    journey_repository = FakeJourneyRepository()
    session_repository = FakeSessionRepository()

    journey = create_learning_journey(
        repository=journey_repository,
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    start_learning_journey(
        repository=journey_repository,
        journey=journey,
        session_repository=session_repository,
    )

    with pytest.raises(
        ValueError,
        match="journey already active",
    ):
        start_learning_journey(
            repository=journey_repository,
            journey=journey,
            session_repository=session_repository,
        )

    assert len(session_repository.saved_sessions) == 1


def test_complete_learning_journey_should_mark_completed():
    class FakeRepository:
        def save(self, journey):
            pass

    repository = FakeRepository()

    journey = create_learning_journey(
        repository=repository,
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    start_learning_journey(
        repository=repository,
        journey=journey,
    )

    completed_journey = complete_learning_journey(
        repository=repository,
        journey=journey,
    )

    assert completed_journey.status == "completed"


def test_complete_learning_journey_should_reject_created_status():
    class FakeRepository:
        def save(self, journey):
            pass

    journey = create_learning_journey(
        repository=FakeRepository(),
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    with pytest.raises(
        ValueError,
        match="only active journey can be completed",
    ):
        complete_learning_journey(
            repository=FakeRepository(),
            journey=journey,
        )


def test_start_learning_journey_should_reject_completed_status():
    class FakeRepository:
        def save(self, journey):
            pass

    journey = create_learning_journey(
        repository=FakeRepository(),
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    start_learning_journey(
        repository=FakeRepository(),
        journey=journey,
    )

    complete_learning_journey(
        repository=FakeRepository(),
        journey=journey,
    )

    with pytest.raises(
        ValueError,
        match="journey already completed",
    ):
        start_learning_journey(
            repository=FakeRepository(),
            journey=journey,
        )


def test_complete_learning_journey_should_reject_completed_status():
    class FakeRepository:
        def save(self, journey):
            pass

    repository = FakeRepository()

    journey = create_learning_journey(
        repository=repository,
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    start_learning_journey(
        repository=repository,
        journey=journey,
    )

    complete_learning_journey(
        repository=repository,
        journey=journey,
    )

    with pytest.raises(
        ValueError,
        match="only active journey can be completed",
    ):
        complete_learning_journey(
            repository=repository,
            journey=journey,
        )


def test_create_journey_with_empty_topics_should_save_empty_curriculum():
    class FakeJourneyRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    class FakeCurriculumRepository:
        def __init__(self):
            self.saved_curriculums = []

        def save(self, curriculum):
            self.saved_curriculums.append(curriculum)

    journey_repository = FakeJourneyRepository()
    curriculum_repository = FakeCurriculumRepository()

    journey = create_learning_journey(
        repository=journey_repository,
        user_id="user_001",
        domain="Python",
        goal="掌握 Python 编程",
        curriculum_topics=[],
        curriculum_repository=curriculum_repository,
    )

    assert journey_repository.saved_journeys == [journey]

    assert len(curriculum_repository.saved_curriculums) == 1

    curriculum = curriculum_repository.saved_curriculums[0]

    assert curriculum.journey_id == journey.journey_id
    assert curriculum.items == []


def test_create_journey_should_reject_non_string_curriculum_topic():
    class FakeJourneyRepository:
        def __init__(self):
            self.saved_journeys = []

        def save(self, journey):
            self.saved_journeys.append(journey)

    class FakeCurriculumRepository:
        def __init__(self):
            self.saved_curriculums = []

        def save(self, curriculum):
            self.saved_curriculums.append(curriculum)

    journey_repository = FakeJourneyRepository()
    curriculum_repository = FakeCurriculumRepository()

    with pytest.raises(
        ValueError,
        match="curriculum_topics must be a list of strings",
    ):
        create_learning_journey(
            repository=journey_repository,
            user_id="user_001",
            domain="Python",
            goal="掌握 Python 编程",
            curriculum_topics=[
                "Python变量",
                123,
            ],
            curriculum_repository=curriculum_repository,
        )

    assert journey_repository.saved_journeys == []
    assert curriculum_repository.saved_curriculums == []
