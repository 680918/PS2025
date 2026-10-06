from memory.memory_score_fusion_benchmark import (
    run_memory_score_fusion_benchmark,
    summarize_memory_score_fusion_benchmark,
)
from memory.memory_score_fusion_regression import (
    check_memory_score_fusion_regression,
)


def test_current_memory_score_fusion_should_pass_regression_baseline():
    results = run_memory_score_fusion_benchmark()

    summary = summarize_memory_score_fusion_benchmark(
        results,
    )

    regression = check_memory_score_fusion_regression(
        summary,
    )

    assert regression["passed"] is True
    assert regression["violations"] == []


def test_memory_score_fusion_regression_should_fail_below_baseline():
    summary = {
        "overall_pairwise_order_accuracy": 0.90,
        "minimum_pairwise_margin": 0.10,
        "average_minimum_pairwise_margin": 0.18,
    }

    regression = check_memory_score_fusion_regression(
        summary,
    )

    assert regression["passed"] is False
    assert regression["violations"] == [
        "overall_pairwise_order_accuracy",
        "minimum_pairwise_margin",
        "average_minimum_pairwise_margin",
    ]


def test_memory_score_fusion_regression_should_report_only_failed_metric():
    summary = {
        "overall_pairwise_order_accuracy": 1.00,
        "minimum_pairwise_margin": 0.10,
        "average_minimum_pairwise_margin": 0.22,
    }

    regression = check_memory_score_fusion_regression(
        summary,
    )

    assert regression["passed"] is False
    assert regression["violations"] == [
        "minimum_pairwise_margin",
    ]
