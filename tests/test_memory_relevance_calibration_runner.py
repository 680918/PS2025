from memory.relevance_calibration_runner import (
    run_relevance_calibration,
)


def test_relevance_calibration_runner_should_return_report():

    result = run_relevance_calibration()

    assert "cases" in result
    assert "average_pairwise_order_accuracy" in result

    assert len(result["cases"]) >= 4
