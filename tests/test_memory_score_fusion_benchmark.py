import pytest

from memory.memory_score_fusion_benchmark import (
    get_memory_score_fusion_benchmark_cases,
    run_memory_score_fusion_benchmark,
    summarize_memory_score_fusion_benchmark,
)


def test_benchmark_cases_should_include_expected_ranking_data():
    cases = get_memory_score_fusion_benchmark_cases()

    assert cases

    first_case = cases[0]

    assert "name" in first_case
    assert "items" in first_case
    assert len(first_case["items"]) >= 2

    for item in first_case["items"]:
        assert "memory_key" in item
        assert "expected_rank" in item
        assert "relevance_score" in item
        assert "importance" in item
        assert "confidence" in item


def test_benchmark_runner_should_evaluate_all_cases():
    results = run_memory_score_fusion_benchmark()

    assert results
    assert len(results) == len(get_memory_score_fusion_benchmark_cases())

    first_result = results[0]

    assert "name" in first_result
    assert "pairwise_order_accuracy" in first_result
    assert "minimum_pairwise_margin" in first_result


def test_benchmark_cases_should_include_quality_tie_break_case():
    cases = get_memory_score_fusion_benchmark_cases()

    case_names = {case["name"] for case in cases}

    assert "quality_should_break_relevance_tie" in case_names


def test_benchmark_runner_should_report_expected_quality_metrics():
    results = run_memory_score_fusion_benchmark()

    results_by_name = {result["name"]: result for result in results}

    relevance_case = results_by_name[
        "relevance_should_dominate_high_quality_distractor"
    ]

    assert relevance_case["pairwise_order_accuracy"] == 1.0
    assert relevance_case["minimum_pairwise_margin"] == pytest.approx(0.16)

    quality_case = results_by_name["quality_should_break_relevance_tie"]

    assert quality_case["pairwise_order_accuracy"] == 1.0
    assert quality_case["minimum_pairwise_margin"] == pytest.approx(0.28)


def test_benchmark_summary_should_report_overall_quality_metrics():
    results = run_memory_score_fusion_benchmark()

    summary = summarize_memory_score_fusion_benchmark(
        results,
    )

    assert summary["overall_pairwise_order_accuracy"] == pytest.approx(1.0)

    assert summary["minimum_pairwise_margin"] == pytest.approx(0.16)

    assert summary["average_minimum_pairwise_margin"] == pytest.approx(0.22)


def test_benchmark_summary_should_return_zero_metrics_when_results_are_empty():
    summary = summarize_memory_score_fusion_benchmark(
        [],
    )

    assert summary == {
        "overall_pairwise_order_accuracy": 0.0,
        "minimum_pairwise_margin": 0.0,
        "average_minimum_pairwise_margin": 0.0,
    }
