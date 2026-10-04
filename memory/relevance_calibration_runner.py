from memory.relevance_calibration import (
    evaluate_calibration_dataset,
)

from memory.relevance_calibration_dataset import (
    get_calibration_cases,
)


def run_relevance_calibration():

    cases = get_calibration_cases()

    return evaluate_calibration_dataset(
        cases,
    )
