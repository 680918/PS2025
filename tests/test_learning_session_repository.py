from learning.session import LearningSession
from learning.session_repository import (
    InMemoryLearningSessionRepository,
)


def test_repository_should_return_latest_session_for_journey():
    repository = InMemoryLearningSessionRepository()

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
        next_step="继续练习参数结构",
    )

    repository.save(first_session)
    repository.save(second_session)

    latest_session = repository.get_latest_by_journey("journey_001")

    assert latest_session is second_session
    assert latest_session.topic == "Tool Calling"
    assert latest_session.next_step == "继续练习参数结构"


def test_repository_should_return_none_when_journey_has_no_sessions():
    repository = InMemoryLearningSessionRepository()

    latest_session = repository.get_latest_by_journey("journey_missing")

    assert latest_session is None
