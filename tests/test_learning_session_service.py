from learning.session_service import (
    create_and_save_learning_session,
    create_learning_session,
)


def test_create_learning_session_should_build_session_from_feedback():
    session = create_learning_session(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        completed=True,
        understanding_score=85,
        difficulty="参数校验还不熟",
        next_step="继续练习 Tool Schema",
    )

    assert session.journey_id == "journey_001"
    assert session.user_id == "user_001"
    assert session.topic == "Tool Calling"
    assert session.completed is True
    assert session.understanding_score == 85
    assert session.difficulty == "参数校验还不熟"
    assert session.next_step == "继续练习 Tool Schema"

    assert session.session_id


def test_create_and_save_learning_session_should_persist_session():
    class FakeRepository:
        def __init__(self):
            self.saved_sessions = []

        def save(self, session):
            self.saved_sessions.append(session)

    repository = FakeRepository()

    session = create_and_save_learning_session(
        repository=repository,
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        completed=True,
        understanding_score=85,
        difficulty="参数校验还不熟",
        next_step="继续练习 Tool Schema",
    )

    assert repository.saved_sessions == [session]
    assert session.journey_id == "journey_001"
    assert session.next_step == "继续练习 Tool Schema"
