from agent.controller import run_agent_runtime
from learning.session_repository import (
    InMemoryLearningSessionRepository,
)
from learning.session_service import (
    create_and_save_learning_session,
)


def test_day2_should_restore_day1_learning_state(
    monkeypatch,
):
    repository = InMemoryLearningSessionRepository()

    create_and_save_learning_session(
        repository=repository,
        journey_id="journey_001",
        user_id="user_001",
        topic="Tool Calling",
        completed=True,
        understanding_score=85,
        difficulty="参数校验还不熟",
        next_step="继续练习 Tool Schema",
    )

    def fake_route_task(user_message):
        return "simple"

    def fake_run_simple_agent(
        user_message,
        state=None,
    ):
        return "继续练习 Tool Schema。"

    monkeypatch.setattr(
        "agent.controller.route_task",
        fake_route_task,
    )

    monkeypatch.setattr(
        "agent.controller.run_simple_agent",
        fake_run_simple_agent,
    )

    state, response = run_agent_runtime(
        user_message="我今天继续学习。",
        journey_id="journey_001",
        learning_session_repository=repository,
    )

    assert state.learning_continuity_context["has_previous_session"] is True

    assert state.learning_continuity_context["topic"] == "Tool Calling"

    assert state.learning_continuity_context["next_step"] == "继续练习 Tool Schema"

    assert response == "继续练习 Tool Schema。"
