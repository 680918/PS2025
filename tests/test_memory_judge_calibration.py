import pytest

from memory.memory_judge_calibration import (
    calculate_delta_correlation,
    calculate_score_bias,
    calculate_score_scale_gap,
)


def test_delta_correlation_should_measure_same_direction():
    rule_deltas = [
        0.25,
        0.0,
        -0.75,
    ]

    llm_deltas = [
        1.0,
        0.0,
        -1.0,
    ]

    result = calculate_delta_correlation(
        rule_deltas,
        llm_deltas,
    )

    assert result > 0.95


def test_score_scale_gap_should_measure_average_difference():
    rule_scores = [
        0.75,
        0.5,
        0.25,
    ]

    llm_scores = [
        0.5,
        0.5,
        0.0,
    ]

    result = calculate_score_scale_gap(
        rule_scores,
        llm_scores,
    )

    assert result == pytest.approx(
        0.166,
        abs=0.01,
    )


def test_calibration_metrics_should_handle_empty_input():
    assert (
        calculate_delta_correlation(
            [],
            [],
        )
        == 0.0
    )

    assert (
        calculate_score_scale_gap(
            [],
            [],
        )
        == 0.0
    )


def test_score_bias_should_expose_judge_strictness_direction():
    rule_scores = [
        0.8,
        0.9,
        0.7,
    ]

    llm_scores = [
        0.5,
        0.6,
        0.4,
    ]

    result = calculate_score_bias(
        rule_scores,
        llm_scores,
    )

    assert result == pytest.approx(-0.30)

    assert (
        calculate_score_bias(
            [],
            [],
        )
        == 0.0
    )
