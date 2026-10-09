import pytest

from memory.memory_pairwise_stability import (
    summarize_pairwise_stability,
)


def _build_report(
    effects,
):
    results = []

    for (
        case_id,
        expected_effect,
        actual_effect,
    ) in effects:
        results.append(
            {
                "case_id": case_id,
                "category": "ambiguous",
                "expected_effect": (expected_effect),
                "pairwise_actual_effect": (actual_effect),
                "is_correct": (expected_effect == actual_effect),
            }
        )

    correct_cases = sum(1 for result in results if result["is_correct"])

    total_cases = len(results)

    return {
        "results": results,
        "summary": {
            "total_cases": total_cases,
            "correct_cases": correct_cases,
            "error_cases": (total_cases - correct_cases),
            "accuracy": (correct_cases / total_cases if total_cases else 0.0),
        },
    }


def test_pairwise_stability_should_report_perfect_stability():
    reports = [
        _build_report(
            [
                (
                    "case-a",
                    "neutral",
                    "neutral",
                ),
                (
                    "case-b",
                    "positive",
                    "positive",
                ),
            ]
        )
        for _ in range(3)
    ]

    result = summarize_pairwise_stability(reports)

    assert result["runs"] == 3

    assert result["run_accuracies"] == [
        1.0,
        1.0,
        1.0,
    ]

    assert result["mean_accuracy"] == pytest.approx(1.0)

    assert result["min_accuracy"] == pytest.approx(1.0)

    assert result["unstable_case_count"] == 0

    assert result["unstable_cases"] == []


def test_pairwise_stability_should_detect_unstable_case():
    reports = [
        _build_report(
            [
                (
                    "case-a",
                    "neutral",
                    "neutral",
                ),
            ]
        ),
        _build_report(
            [
                (
                    "case-a",
                    "neutral",
                    "positive",
                ),
            ]
        ),
        _build_report(
            [
                (
                    "case-a",
                    "neutral",
                    "neutral",
                ),
            ]
        ),
    ]

    result = summarize_pairwise_stability(reports)

    assert result["unstable_case_count"] == 1

    case = result["unstable_cases"][0]

    assert case["case_id"] == "case-a"

    assert case["observed_effects"] == [
        "neutral",
        "positive",
        "neutral",
    ]

    assert case["gold_accuracy"] == pytest.approx(2 / 3)

    assert case["effect_consistent"] is False


def test_pairwise_stability_should_handle_empty_reports():
    result = summarize_pairwise_stability([])

    assert result == {
        "runs": 0,
        "run_accuracies": [],
        "mean_accuracy": 0.0,
        "min_accuracy": 0.0,
        "max_accuracy": 0.0,
        "total_cases": 0,
        "stable_correct_cases": 0,
        "unstable_case_count": 0,
        "unstable_cases": [],
        "case_results": [],
        "consensus_correct_cases": 0,
        "consensus_accuracy": 0.0,
    }


def test_pairwise_stability_should_report_consensus():
    reports = [
        _build_report(
            [
                (
                    "case-a",
                    "positive",
                    "positive",
                ),
            ]
        ),
        _build_report(
            [
                (
                    "case-a",
                    "positive",
                    "positive",
                ),
            ]
        ),
        _build_report(
            [
                (
                    "case-a",
                    "positive",
                    "neutral",
                ),
            ]
        ),
    ]

    result = summarize_pairwise_stability(reports)

    case = result["case_results"][0]

    assert case["consensus_effect"] == "positive"

    assert case["consensus_rate"] == pytest.approx(2 / 3)

    assert case["consensus_correct"] is True

    assert result["consensus_correct_cases"] == 1

    assert result["consensus_accuracy"] == pytest.approx(1.0)


def test_pairwise_stability_should_report_no_consensus_on_tie():
    reports = [
        _build_report(
            [
                (
                    "case-a",
                    "neutral",
                    "neutral",
                ),
            ]
        ),
        _build_report(
            [
                (
                    "case-a",
                    "neutral",
                    "positive",
                ),
            ]
        ),
    ]

    result = summarize_pairwise_stability(reports)

    case = result["case_results"][0]

    assert case["consensus_effect"] is None

    assert case["consensus_rate"] == pytest.approx(0.5)

    assert case["consensus_correct"] is False
