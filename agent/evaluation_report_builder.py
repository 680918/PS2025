from agent.evaluation_report import (
    EvaluationReport,
)


def build_evaluation_report(
    evaluations,
):

    total_checks = 0
    passed_checks = 0
    failed_checks = 0

    for category_results in evaluations.values():
        for result in category_results.values():
            total_checks += 1

            if result.passed:
                passed_checks += 1
            else:
                failed_checks += 1

    return EvaluationReport(
        passed=failed_checks == 0,
        evaluations=evaluations,
        summary={
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
        },
    )
