from memory.memory_contribution_runner import (
    run_memory_contribution_llm_evaluation,
    run_memory_contribution_rule_evaluation,
)
from memory.memory_judge_calibration import (
    calculate_delta_correlation,
    calculate_score_bias,
    calculate_score_scale_gap,
)


def _index_results_by_case(
    results,
):
    return {result["case_id"]: result for result in results}


def compare_memory_contribution_judges(
    cases,
    answer_provider,
    llm_call,
):
    rule_report = run_memory_contribution_rule_evaluation(
        cases,
        answer_provider=answer_provider,
    )

    llm_report = run_memory_contribution_llm_evaluation(
        cases,
        answer_provider=answer_provider,
        llm_call=llm_call,
    )

    rule_results = _index_results_by_case(rule_report["results"])

    llm_results = _index_results_by_case(llm_report["results"])

    comparisons = []

    for case in cases:
        case_id = case["case_id"]

        rule_result = rule_results[case_id]

        llm_result = llm_results[case_id]

        rule_actual_effect = rule_result["actual_effect"]

        llm_actual_effect = llm_result["actual_effect"]

        effect_agreement = rule_actual_effect == llm_actual_effect

        rule_delta = rule_result["contribution_delta"]

        llm_delta = llm_result["contribution_delta"]

        comparisons.append(
            {
                "case_id": case_id,
                "expected_effect": case["expected_effect"],
                "rule_actual_effect": (rule_actual_effect),
                "llm_actual_effect": (llm_actual_effect),
                "effect_agreement": (effect_agreement),
                "rule_contribution_delta": (rule_delta),
                "llm_contribution_delta": (llm_delta),
                "contribution_delta_gap": abs(rule_delta - llm_delta),
                "rule_without_memory_score": (rule_result["without_memory_score"]),
                "llm_without_memory_score": (llm_result["without_memory_score"]),
                "without_memory_score_gap": abs(
                    rule_result["without_memory_score"]
                    - llm_result["without_memory_score"]
                ),
                "rule_with_memory_score": (rule_result["with_memory_score"]),
                "llm_with_memory_score": (llm_result["with_memory_score"]),
                "with_memory_score_gap": abs(
                    rule_result["with_memory_score"] - llm_result["with_memory_score"]
                ),
                "llm_without_memory_reason": (
                    llm_result["without_memory_quality"]["reason"]
                ),
                "llm_with_memory_reason": (llm_result["with_memory_quality"]["reason"]),
            }
        )

    return {
        "comparisons": comparisons,
        "summary": summarize_judge_comparisons(comparisons),
    }


def summarize_judge_comparisons(
    comparisons,
):
    total_cases = len(comparisons)

    effect_agreements = sum(
        1 for comparison in comparisons if comparison["effect_agreement"]
    )

    effect_disagreements = total_cases - effect_agreements

    if total_cases:
        effect_agreement_rate = effect_agreements / total_cases

        mean_contribution_delta_gap = (
            sum(comparison["contribution_delta_gap"] for comparison in comparisons)
            / total_cases
        )
    else:
        effect_agreement_rate = 0.0
        mean_contribution_delta_gap = 0.0

    rule_deltas = [comparison["rule_contribution_delta"] for comparison in comparisons]

    llm_deltas = [comparison["llm_contribution_delta"] for comparison in comparisons]

    rule_scores = []
    llm_scores = []

    for comparison in comparisons:
        rule_scores.extend(
            [
                comparison["rule_without_memory_score"],
                comparison["rule_with_memory_score"],
            ]
        )

        llm_scores.extend(
            [
                comparison["llm_without_memory_score"],
                comparison["llm_with_memory_score"],
            ]
        )

    delta_correlation = calculate_delta_correlation(
        rule_deltas,
        llm_deltas,
    )

    score_scale_gap = calculate_score_scale_gap(
        rule_scores,
        llm_scores,
    )

    score_bias = calculate_score_bias(
        rule_scores,
        llm_scores,
    )

    return {
        "total_cases": total_cases,
        "effect_agreements": (effect_agreements),
        "effect_disagreements": (effect_disagreements),
        "effect_agreement_rate": (effect_agreement_rate),
        "mean_contribution_delta_gap": (mean_contribution_delta_gap),
        "delta_correlation": (delta_correlation),
        "score_scale_gap": (score_scale_gap),
        "score_bias": (score_bias),
    }
