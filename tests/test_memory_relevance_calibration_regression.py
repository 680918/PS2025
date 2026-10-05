import pytest
from memory.relevance_calibration_regression import (
    evaluate_calibration_regression,
)
from memory.relevance_calibration_runner import (
    run_relevance_calibration_regression,
)


def test_calibration_regression_should_detect_metric_drop():
    baseline = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.33,
        "average_minimum_pairwise_margin": 0.46,
    }

    current = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.20,
        "average_minimum_pairwise_margin": 0.46,
    }

    result = evaluate_calibration_regression(
        current=current,
        baseline=baseline,
    )

    assert result["passed"] is False
    assert "minimum_pairwise_margin" in result["regressions"]


def test_calibration_regression_should_pass_when_metrics_do_not_drop():
    baseline = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.33,
        "average_minimum_pairwise_margin": 0.46,
    }

    current = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.40,
        "average_minimum_pairwise_margin": 0.50,
    }

    result = evaluate_calibration_regression(
        current=current,
        baseline=baseline,
    )

    assert result["passed"] is True
    assert result["regressions"] == []


def test_current_calibration_should_pass_regression_baseline():
    result = run_relevance_calibration_regression()

    assert result["passed"] is True
    assert result["regressions"] == []


def test_calibration_regression_should_report_metric_values():
    baseline = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.33,
        "average_minimum_pairwise_margin": 0.46,
    }

    current = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.20,
        "average_minimum_pairwise_margin": 0.40,
    }

    result = evaluate_calibration_regression(
        current=current,
        baseline=baseline,
    )

    assert result["baseline"] == baseline
    assert result["current"] == current


def test_calibration_regression_should_report_metric_deltas():
    baseline = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.33,
        "average_minimum_pairwise_margin": 0.46,
    }

    current = {
        "pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.20,
        "average_minimum_pairwise_margin": 0.40,
    }

    result = evaluate_calibration_regression(
        current=current,
        baseline=baseline,
    )

    assert "deltas" in result

    assert result["deltas"]["pairwise_order_accuracy"] == 0.0
    assert result["deltas"]["minimum_pairwise_margin"] == pytest.approx(-0.13)
    assert result["deltas"]["average_minimum_pairwise_margin"] == pytest.approx(-0.06)
