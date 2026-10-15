from agent.context_evaluation import (
    ContextEvaluationResult,
)


def test_context_evaluation_result_should_record_success():

    result = ContextEvaluationResult(
        success=True,
        expected_source="memory",
        actual_source="memory",
        policy="COMPLETED_LEARNING_POLICY",
    )

    assert result.success is True

    assert result.expected_source == "memory"

    assert result.actual_source == "memory"

    assert result.policy == ("COMPLETED_LEARNING_POLICY")


def test_context_evaluation_result_should_record_failure():

    result = ContextEvaluationResult(
        success=False,
        expected_source="memory",
        actual_source="conversation",
        policy="COMPLETED_LEARNING_POLICY",
    )

    assert result.success is False

    assert result.expected_source == "memory"

    assert result.actual_source == "conversation"


def test_context_evaluation_result_should_support_learning_policy():

    result = ContextEvaluationResult(
        success=True,
        expected_source="conversation",
        actual_source="conversation",
        policy="LEARNING_POLICY",
    )

    assert result.policy == ("LEARNING_POLICY")
