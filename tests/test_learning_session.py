from learning.session import LearningSession
from datetime import datetime


def test_learning_session_should_store_core_session_context():
    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
    )

    assert session.journey_id == "journey_001"
    assert session.user_id == "user_001"
    assert session.topic == "Tool Calling"


def test_learning_session_should_store_learning_result():
    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        completed=True,
        understanding_score=80,
        difficulty="参数结构还不熟",
        next_step="继续练习工具参数和返回结果",
    )

    assert session.completed is True
    assert session.understanding_score == 80
    assert session.difficulty == "参数结构还不熟"
    assert session.next_step == "继续练习工具参数和返回结果"


def test_learning_session_should_have_identity_and_timestamps():
    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
    )

    assert isinstance(session.session_id, str)
    assert session.session_id

    assert isinstance(session.created_at, datetime)
    assert isinstance(session.updated_at, datetime)

    assert session.updated_at >= session.created_at
