BASELINE_OVERALL_PAIRWISE_ORDER_ACCURACY = 1.00
BASELINE_MINIMUM_PAIRWISE_MARGIN = 0.16
BASELINE_AVERAGE_MINIMUM_PAIRWISE_MARGIN = 0.22

FLOAT_TOLERANCE = 1e-9


def check_memory_score_fusion_regression(
    summary,
):
    violations = []

    if (
        summary["overall_pairwise_order_accuracy"] + FLOAT_TOLERANCE
        < BASELINE_OVERALL_PAIRWISE_ORDER_ACCURACY
    ):
        violations.append("overall_pairwise_order_accuracy")

    if (
        summary["minimum_pairwise_margin"] + FLOAT_TOLERANCE
        < BASELINE_MINIMUM_PAIRWISE_MARGIN
    ):
        violations.append("minimum_pairwise_margin")

    if (
        summary["average_minimum_pairwise_margin"] + FLOAT_TOLERANCE
        < BASELINE_AVERAGE_MINIMUM_PAIRWISE_MARGIN
    ):
        violations.append("average_minimum_pairwise_margin")

    return {
        "passed": not violations,
        "violations": violations,
    }
