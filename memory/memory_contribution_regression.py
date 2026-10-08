from memory.memory_contribution_regression_baseline import (
    MEMORY_CONTRIBUTION_REGRESSION_BASELINE,
)

FLOAT_TOLERANCE = 1e-9


def evaluate_memory_contribution_regression(
    report,
    baseline=None,
):
    if baseline is None:
        baseline = MEMORY_CONTRIBUTION_REGRESSION_BASELINE

    failures = []

    summary = report["summary"]

    expected_total_cases = baseline["total_cases"]

    actual_total_cases = summary["total_cases"]

    if actual_total_cases != expected_total_cases:
        failures.append(
            (
                "total_cases regression: "
                f"expected={expected_total_cases} "
                f"actual={actual_total_cases}"
            )
        )

    expected_accuracy = baseline["accuracy"]

    actual_accuracy = summary["accuracy"]

    if abs(actual_accuracy - expected_accuracy) > FLOAT_TOLERANCE:
        failures.append(
            (
                "accuracy regression: "
                f"expected={expected_accuracy} "
                f"actual={actual_accuracy}"
            )
        )

    results_by_case = {result["case_id"]: result for result in report["results"]}

    for (
        case_id,
        expected_case,
    ) in baseline["cases"].items():
        actual_case = results_by_case.get(case_id)

        if actual_case is None:
            failures.append(f"missing case: {case_id}")
            continue

        expected_effect = expected_case["actual_effect"]

        actual_effect = actual_case["actual_effect"]

        if actual_effect != expected_effect:
            failures.append(
                (
                    f"{case_id} actual_effect "
                    f"regression: "
                    f"expected={expected_effect} "
                    f"actual={actual_effect}"
                )
            )

        expected_delta = expected_case["contribution_delta"]

        actual_delta = actual_case["contribution_delta"]

        if abs(actual_delta - expected_delta) > FLOAT_TOLERANCE:
            failures.append(
                (
                    f"{case_id} "
                    "contribution_delta "
                    "regression: "
                    f"expected={expected_delta} "
                    f"actual={actual_delta}"
                )
            )

    return {
        "passed": not failures,
        "failures": failures,
    }
