from memory.retrieval_benchmark_report import (
    summarize_benchmark_results,
)


def test_benchmark_report_should_calculate_average_f1():

    results = [
        {
            "name": "case_a",
            "metrics": {
                1: {
                    "f1_at_k": 0.5,
                },
                2: {
                    "f1_at_k": 1.0,
                },
            },
        },
        {
            "name": "case_b",
            "metrics": {
                1: {
                    "f1_at_k": 1.0,
                },
                2: {
                    "f1_at_k": 0.5,
                },
            },
        },
    ]

    report = summarize_benchmark_results(results)

    assert report["average_f1_by_k"][1] == 0.75
    assert report["average_f1_by_k"][2] == 0.75


def test_benchmark_report_should_include_case_names():

    results = [
        {
            "name": "python_tool_calling",
            "metrics": {
                1: {
                    "f1_at_k": 0.5,
                }
            },
        },
        {
            "name": "agent_memory",
            "metrics": {
                1: {
                    "f1_at_k": 1.0,
                }
            },
        },
    ]

    report = summarize_benchmark_results(results)

    assert "cases" in report

    assert "python_tool_calling" in report["cases"]

    assert "agent_memory" in report["cases"]


def test_benchmark_report_should_include_retrieval_efficiency_metrics():

    results = [
        {
            "name": "test_case",
            "metrics": {
                1: {
                    "f1_at_k": 1.0,
                    "retrieved_count": 1,
                    "compression_ratio": 0.0,
                },
                3: {
                    "f1_at_k": 1.0,
                    "retrieved_count": 1,
                    "compression_ratio": 2 / 3,
                },
            },
        }
    ]

    report = summarize_benchmark_results(
        results,
    )

    assert "average_retrieved_count_by_k" in report

    assert "average_compression_ratio_by_k" in report
