import pytest

from memory.memory_contribution_evaluator import (
    calculate_contribution_delta,
    classify_contribution_effect,
    evaluate_memory_contribution_case,
    evaluate_memory_contribution_results,
)


def test_calculate_contribution_delta_should_measure_quality_change():
    delta = calculate_contribution_delta(
        without_memory_score=0.60,
        with_memory_score=0.82,
    )

    assert delta == pytest.approx(0.22)


@pytest.mark.parametrize(
    (
        "without_memory_score",
        "with_memory_score",
        "expected_effect",
    ),
    [
        (0.60, 0.82, "positive"),
        (0.60, 0.62, "neutral"),
        (0.80, 0.60, "negative"),
    ],
)
def test_classify_contribution_effect_should_detect_direction(
    without_memory_score,
    with_memory_score,
    expected_effect,
):
    effect = classify_contribution_effect(
        without_memory_score,
        with_memory_score,
    )

    assert effect == expected_effect


def test_evaluate_memory_contribution_case_should_compare_with_expected_effect():
    case = {
        "case_id": "relevant-memory",
        "expected_effect": "positive",
    }

    result = evaluate_memory_contribution_case(
        case,
        without_memory_score=0.55,
        with_memory_score=0.80,
    )

    assert result["case_id"] == "relevant-memory"
    assert result["contribution_delta"] == pytest.approx(0.25)
    assert result["actual_effect"] == "positive"
    assert result["expected_effect"] == "positive"
    assert result["passed"] is True


def test_evaluate_memory_contribution_results_should_report_accuracy():
    results = [
        {
            "case_id": "positive-case",
            "passed": True,
        },
        {
            "case_id": "neutral-case",
            "passed": True,
        },
        {
            "case_id": "negative-case",
            "passed": False,
        },
    ]

    summary = evaluate_memory_contribution_results(results)

    assert summary["total_cases"] == 3
    assert summary["passed_cases"] == 2
    assert summary["failed_cases"] == 1
    assert summary["accuracy"] == pytest.approx(2 / 3)
