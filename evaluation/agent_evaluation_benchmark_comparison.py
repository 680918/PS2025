METRIC_NAMES = (
    "goal_alignment",
    "actionability",
    "memory_usage",
    "knowledge_usage",
    "response_policy",
    "overall_score",
)


def compare_agent_evaluation_benchmarks(
    previous,
    current,
    tolerance=1e-9,
):
    previous_metrics = previous["average_metrics"]
    current_metrics = current["average_metrics"]

    comparison = {}

    for metric_name in METRIC_NAMES:
        comparison[f"{metric_name}_delta"] = (
            current_metrics[metric_name] - previous_metrics[metric_name]
        )

    overall_score_delta = comparison["overall_score_delta"]

    if overall_score_delta > tolerance:
        status = "improved"
    elif overall_score_delta < -tolerance:
        status = "regressed"
    else:
        status = "unchanged"

    comparison["status"] = status

    return comparison
