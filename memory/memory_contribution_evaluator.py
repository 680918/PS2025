from memory.memory_answer_quality import (
    validate_answer_quality_score,
)

CONTRIBUTION_NEUTRAL_THRESHOLD = 0.05


def calculate_contribution_delta(
    without_memory_score,
    with_memory_score,
):
    return with_memory_score - without_memory_score


def classify_contribution_effect(
    without_memory_score,
    with_memory_score,
    neutral_threshold=CONTRIBUTION_NEUTRAL_THRESHOLD,
):
    delta = calculate_contribution_delta(
        without_memory_score,
        with_memory_score,
    )

    if delta > neutral_threshold:
        return "positive"

    if delta < -neutral_threshold:
        return "negative"

    return "neutral"


def evaluate_memory_contribution_case(
    case,
    without_memory_score,
    with_memory_score,
):

    without_memory_score = validate_answer_quality_score(without_memory_score)

    with_memory_score = validate_answer_quality_score(with_memory_score)

    contribution_delta = calculate_contribution_delta(
        without_memory_score,
        with_memory_score,
    )

    actual_effect = classify_contribution_effect(
        without_memory_score,
        with_memory_score,
    )

    expected_effect = case["expected_effect"]

    return {
        "case_id": case["case_id"],
        "without_memory_score": (without_memory_score),
        "with_memory_score": (with_memory_score),
        "contribution_delta": (contribution_delta),
        "actual_effect": actual_effect,
        "expected_effect": expected_effect,
        "passed": (actual_effect == expected_effect),
    }


def evaluate_memory_contribution_results(
    results,
):
    total_cases = len(results)

    passed_cases = sum(1 for result in results if result["passed"])

    failed_cases = total_cases - passed_cases

    if total_cases == 0:
        accuracy = 0.0
    else:
        accuracy = passed_cases / total_cases

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "accuracy": accuracy,
    }
