def _count_by_category(
    comparisons,
):
    counts = {}

    for comparison in comparisons:
        category = comparison["category"]

        counts[category] = (
            counts.get(
                category,
                0,
            )
            + 1
        )

    return counts


def analyze_memory_calibration_errors(
    report,
):
    comparisons = report["comparisons"]

    llm_gold_errors = [
        comparison
        for comparison in comparisons
        if comparison["llm_actual_effect"] != comparison["expected_effect"]
    ]

    rule_gold_errors = [
        comparison
        for comparison in comparisons
        if comparison["rule_actual_effect"] != comparison["expected_effect"]
    ]

    judge_disagreements = [
        comparison for comparison in comparisons if not comparison["effect_agreement"]
    ]

    return {
        "total_cases": len(comparisons),
        "llm_gold_error_count": len(llm_gold_errors),
        "rule_gold_error_count": len(rule_gold_errors),
        "judge_disagreement_count": len(judge_disagreements),
        "llm_gold_errors": (llm_gold_errors),
        "rule_gold_errors": (rule_gold_errors),
        "judge_disagreements": (judge_disagreements),
        "llm_errors_by_category": (_count_by_category(llm_gold_errors)),
    }
