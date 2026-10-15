from agent.evaluation_report import (
    EvaluationReport,
)


def test_evaluation_report_should_store_results():

    report = EvaluationReport(
        passed=True,
        evaluations={
            "policy_compliance": "ok",
        },
        summary={
            "total_checks": 1,
            "passed_checks": 1,
            "failed_checks": 0,
        },
    )

    assert report.passed is True

    assert report.evaluations["policy_compliance"] == "ok"

    assert report.summary["total_checks"] == 1
