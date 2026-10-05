from memory.relevance_calibration_baseline import (
    get_calibration_baseline,
)


def test_calibration_baseline_should_capture_current_metrics():
    baseline = get_calibration_baseline()

    assert baseline["pairwise_order_accuracy"] == 1.0
    assert baseline["minimum_pairwise_margin"] == 0.33
    assert baseline["average_minimum_pairwise_margin"] == 0.46
