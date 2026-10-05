from memory.relevance_calibration import (
    evaluate_calibration_dataset,
)
from memory.relevance_calibration_baseline import (
    get_calibration_baseline,
)
from memory.relevance_calibration_dataset import (
    get_calibration_cases,
)
from memory.relevance_calibration_regression import (
    evaluate_calibration_regression,
)


def run_relevance_calibration():
    cases = get_calibration_cases()

    return evaluate_calibration_dataset(
        cases,
    )


def run_relevance_calibration_regression(
    calibration_report=None,
):
    if calibration_report is None:
        calibration_report = run_relevance_calibration()

    baseline = get_calibration_baseline()

    current_metrics = {
        "pairwise_order_accuracy": calibration_report[
            "average_pairwise_order_accuracy"
        ],
        "minimum_pairwise_margin": calibration_report["minimum_pairwise_margin"],
        "average_minimum_pairwise_margin": calibration_report[
            "average_minimum_pairwise_margin"
        ],
    }

    return evaluate_calibration_regression(
        current=current_metrics,
        baseline=baseline,
    )
