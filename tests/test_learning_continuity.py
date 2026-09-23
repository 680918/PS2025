from learning.continuity import (
    build_learning_continuity_context,
)
from learning.session import LearningSession
from learning.session_repository import (
    InMemoryLearningSessionRepository,
)


def test_build_learning_continuity_context_should_restore_latest_session():
    repository = InMemoryLearningSessionRepository()

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        completed=True,
        understanding_score=80,
        difficulty="参数结构还不熟",
        next_step="继续练习参数结构",
    )

    repository.save(session)

    context = build_learning_continuity_context(
        journey_id="journey_001",
        repository=repository,
    )

    assert context["has_previous_session"] is True
    assert context["session_id"] == session.session_id
    assert context["topic"] == "Tool Calling"
    assert context["completed"] is True
    assert context["understanding_score"] == 80
    assert context["difficulty"] == "参数结构还不熟"
    assert context["next_step"] == "继续练习参数结构"


def test_build_learning_continuity_context_should_handle_first_session():
    repository = InMemoryLearningSessionRepository()

    context = build_learning_continuity_context(
        journey_id="journey_new",
        repository=repository,
    )

    assert context == {
        "has_previous_session": False,
    }


def test_build_learning_continuity_context_should_use_user_ownership():
    class FakeRepository:
        def get_latest_by_journey_for_user(
            self,
            journey_id,
            user_id,
        ):
            assert journey_id == "journey_001"
            assert user_id == "user_001"

            class Session:
                session_id = "session_user_001"
                topic = "Tool Calling"
                completed = True
                understanding_score = 85
                difficulty = "参数校验还不熟"
                next_step = "继续练习 Tool Schema"

            return Session()

    context = build_learning_continuity_context(
        journey_id="journey_001",
        user_id="user_001",
        repository=FakeRepository(),
    )

    assert context["has_previous_session"] is True
    assert context["topic"] == "Tool Calling"
    assert context["next_step"] == "继续练习 Tool Schema"
    assert context["session_id"] == "session_user_001"
