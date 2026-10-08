import pytest

from memory.memory_contribution_benchmark import (
    run_memory_contribution_benchmark,
)


def test_memory_contribution_benchmark_should_pass_builtin_cases():
    report = run_memory_contribution_benchmark()

    assert report["summary"]["total_cases"] == 3
    assert report["summary"]["passed_cases"] == 3
    assert report["summary"]["failed_cases"] == 0

    assert report["summary"]["accuracy"] == pytest.approx(1.0)


def test_memory_contribution_benchmark_should_cover_all_effect_types():
    report = run_memory_contribution_benchmark()

    actual_effects = {result["actual_effect"] for result in report["results"]}

    assert actual_effects == {
        "positive",
        "neutral",
        "negative",
    }


def test_memory_contribution_benchmark_should_preserve_answers_and_scores():
    report = run_memory_contribution_benchmark()

    results_by_case = {result["case_id"]: result for result in report["results"]}

    positive_result = results_by_case["relevant-learning-memory-should-help"]

    assert (
        positive_result["with_memory_score"] > positive_result["without_memory_score"]
    )

    negative_result = results_by_case["contradictory-learning-memory-should-hurt"]

    assert (
        negative_result["with_memory_score"] < negative_result["without_memory_score"]
    )
