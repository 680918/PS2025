from scripts.run_memory_retrieval_benchmark import (
    build_benchmark_output,
)
from unittest.mock import patch


def test_build_benchmark_output_should_return_report_text():

    output = build_benchmark_output()

    assert "Memory Retrieval Benchmark" in output


def test_build_benchmark_output_should_support_score_gap_threshold():

    output = build_benchmark_output(
        threshold=0.5,
        score_gap_threshold=0.4,
    )

    assert "Memory Retrieval Benchmark" in output


def test_build_benchmark_output_should_forward_retrieval_policy_parameters():

    with patch(
        "scripts.run_memory_retrieval_benchmark.run_retrieval_benchmark"
    ) as mock_run:
        mock_run.return_value = []

        build_benchmark_output(
            threshold=0.5,
            score_gap_threshold=0.4,
        )

        mock_run.assert_called_once_with(
            k_values=[1, 2, 3],
            threshold=0.5,
            score_gap_threshold=0.4,
        )
