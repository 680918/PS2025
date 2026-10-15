from agent.evaluation_report_builder import (
    build_evaluation_report,
)

from agent.evaluation_models import (
    EvaluationResult,
)


def test_build_evaluation_report_should_aggregate_results():

    evaluations = {
        "policy_compliance": {
            "learning.current_topic": EvaluationResult(
                metric="policy_compliance",
                passed=True,
                details={},
            )
        },
        "conflict_detection": {
            "learning.current_topic": EvaluationResult(
                metric="conflict_detection",
                passed=False,
                details={},
            )
        },
    }

    report = build_evaluation_report(
        evaluations,
    )

    assert report.summary["total_checks"] == 2

    assert report.summary["passed_checks"] == 1

    assert report.summary["failed_checks"] == 1

    assert report.passed is False
