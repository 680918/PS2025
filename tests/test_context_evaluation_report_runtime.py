from agent.controller import run_agent_runtime
from agent.evaluation_report import (
    EvaluationReport,
)


def test_runtime_should_create_context_evaluation_report():

    state, _ = run_agent_runtime(
        user_message="continue learning",
        conversation_context=[
            {
                "role": "user",
                "content": "I want to learn Memory",
            }
        ],
        learning_continuity_context={
            "has_current_session": True,
            "current_topic": "Tool Calling",
        },
    )

    assert state.context_evaluation_report is not None

    assert isinstance(
        state.context_evaluation_report,
        EvaluationReport,
    )

    assert "total_checks" in state.context_evaluation_report.summary
