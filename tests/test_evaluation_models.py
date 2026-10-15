from agent.evaluation_models import (
    EvaluationResult,
)


def test_evaluation_result_should_store_metric():

    result = EvaluationResult(
        metric="policy_compliance",
        passed=True,
        details={"field": "learning.current_topic"},
    )

    assert result.metric == "policy_compliance"

    assert result.passed is True

    assert result.details["field"] == "learning.current_topic"
