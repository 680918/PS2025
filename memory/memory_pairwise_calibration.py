from memory.memory_calibration_dataset import (
    get_memory_calibration_cases,
)
from memory.memory_llm_pairwise_judge import (
    judge_memory_contribution_pair,
)


_CATEGORIES = (
    "helpful",
    "neutral",
    "harmful",
    "ambiguous",
)


def _summarize_results(
    results,
):
    total_cases = len(results)

    if total_cases == 0:
        return {
            "total_cases": 0,
            "correct_cases": 0,
            "error_cases": 0,
            "accuracy": 0.0,
        }

    correct_cases = sum(1 for result in results if result["is_correct"])

    return {
        "total_cases": total_cases,
        "correct_cases": correct_cases,
        "error_cases": (total_cases - correct_cases),
        "accuracy": (correct_cases / total_cases),
    }


def _build_category_summary(
    results,
):
    summary = {}

    for category in _CATEGORIES:
        category_results = [
            result for result in results if result["category"] == category
        ]

        summary[category] = _summarize_results(category_results)

    return summary


def run_memory_pairwise_calibration(
    llm_call,
    cases=None,
):
    if cases is None:
        cases = get_memory_calibration_cases()

    results = []

    for case in cases:
        answers = case["benchmark_answers"]

        judgment = judge_memory_contribution_pair(
            query=case["query"],
            without_memory_answer=(answers["without_memory"]),
            with_memory_answer=(answers["with_memory"]),
            evaluation_criteria=(case["evaluation_criteria"]),
            llm_call=llm_call,
        )

        actual_effect = judgment["effect"]

        result = {
            "case_id": case["case_id"],
            "category": case["category"],
            "domain": case["domain"],
            "description": case["description"],
            "expected_effect": case["expected_effect"],
            "pairwise_actual_effect": (actual_effect),
            "pairwise_reason": judgment["reason"],
            "is_correct": (actual_effect == case["expected_effect"]),
        }

        results.append(result)

    errors = [result for result in results if not result["is_correct"]]

    return {
        "results": results,
        "summary": (_summarize_results(results)),
        "category_summary": (_build_category_summary(results)),
        "errors": errors,
    }
