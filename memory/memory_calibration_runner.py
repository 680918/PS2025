from memory.memory_calibration_dataset import (
    get_memory_calibration_cases,
)
from memory.memory_judge_benchmark import (
    create_benchmark_answer_provider,
)
from memory.memory_judge_comparison import (
    compare_memory_contribution_judges,
    summarize_judge_comparisons,
)


def _calculate_expected_accuracy(
    comparisons,
    effect_field,
):
    if not comparisons:
        return 0.0

    matches = sum(
        1
        for comparison in comparisons
        if comparison[effect_field] == comparison["expected_effect"]
    )

    return matches / len(comparisons)


def _summarize_calibration_comparisons(
    comparisons,
):
    summary = summarize_judge_comparisons(comparisons)

    return {
        **summary,
        "rule_expected_accuracy": (
            _calculate_expected_accuracy(
                comparisons,
                "rule_actual_effect",
            )
        ),
        "llm_expected_accuracy": (
            _calculate_expected_accuracy(
                comparisons,
                "llm_actual_effect",
            )
        ),
    }


def _build_category_summary(
    comparisons,
):
    grouped = {}

    for comparison in comparisons:
        category = comparison["category"]

        grouped.setdefault(
            category,
            [],
        ).append(comparison)

    return {
        category: (_summarize_calibration_comparisons(category_comparisons))
        for (
            category,
            category_comparisons,
        ) in grouped.items()
    }


def run_memory_calibration(
    llm_call,
    cases=None,
):
    if cases is None:
        cases = get_memory_calibration_cases()

    comparisons = []

    for case in cases:
        answer_provider = create_benchmark_answer_provider(case)

        report = compare_memory_contribution_judges(
            [case],
            answer_provider=answer_provider,
            llm_call=llm_call,
        )

        comparison = {
            **report["comparisons"][0],
            "category": case["category"],
            "domain": case["domain"],
            "description": case["description"],
        }

        comparisons.append(comparison)

    return {
        "comparisons": comparisons,
        "summary": (_summarize_calibration_comparisons(comparisons)),
        "category_summary": (_build_category_summary(comparisons)),
    }
