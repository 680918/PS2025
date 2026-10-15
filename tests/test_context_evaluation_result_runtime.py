from agent.controller import run_agent_runtime
from agent.evaluation_models import EvaluationResult


def test_runtime_should_store_evaluation_result_objects():

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

    result = state.context_evaluation_results["policy_compliance"][
        "learning.current_topic"
    ]

    assert isinstance(
        result,
        EvaluationResult,
    )

    assert result.passed is True
