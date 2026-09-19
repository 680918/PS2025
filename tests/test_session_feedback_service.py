import pytest

from learning.session import LearningSession
from learning.session_service import (
    update_learning_session_feedback,
)


def test_update_learning_session_feedback_should_update_and_save_session():
    class FakeRepository:
        def __init__(self):
            self.saved_sessions = []

        def save(self, session):
            self.saved_sessions.append(session)

    repository = FakeRepository()

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="英语",
    )

    updated_session = update_learning_session_feedback(
        repository=repository,
        session=session,
        understanding_score=80,
        difficulty="听力速度较快",
        next_step="练习慢速英语听力",
    )

    assert updated_session.completed is True
    assert updated_session.understanding_score == 80
    assert updated_session.difficulty == "听力速度较快"
    assert updated_session.next_step == "练习慢速英语听力"

    assert len(repository.saved_sessions) == 1
    assert repository.saved_sessions[0] is updated_session


def test_update_learning_session_feedback_should_reject_invalid_score():
    class FakeRepository:
        def save(self, session):
            raise AssertionError("invalid feedback should not be saved")

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="英语",
    )

    with pytest.raises(
        ValueError,
        match="understanding_score must be between 0 and 100",
    ):
        update_learning_session_feedback(
            repository=FakeRepository(),
            session=session,
            understanding_score=120,
            difficulty="听力速度较快",
            next_step="练习慢速英语听力",
        )


def test_update_learning_session_feedback_should_reject_empty_difficulty():
    class FakeRepository:
        def save(self, session):
            raise AssertionError("invalid feedback should not be saved")

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="英语",
    )

    with pytest.raises(
        ValueError,
        match="difficulty is required",
    ):
        update_learning_session_feedback(
            repository=FakeRepository(),
            session=session,
            understanding_score=80,
            difficulty="   ",
            next_step="练习慢速英语听力",
        )


def test_update_learning_session_feedback_should_reject_empty_next_step():
    class FakeRepository:
        def save(self, session):
            raise AssertionError("invalid feedback should not be saved")

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="英语",
    )

    with pytest.raises(
        ValueError,
        match="next_step is required",
    ):
        update_learning_session_feedback(
            repository=FakeRepository(),
            session=session,
            understanding_score=80,
            difficulty="听力速度较快",
            next_step="   ",
        )
