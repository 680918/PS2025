from memory.retrieval_benchmark_cli import (
    format_benchmark_report,
)


def test_format_benchmark_report_should_include_title():

    report = {
        "average_f1_by_k": {
            1: 0.5,
            2: 1.0,
        }
    }

    output = format_benchmark_report(report)

    assert "Memory Retrieval Benchmark" in output
    assert "K=1" in output
    assert "K=2" in output


def test_format_benchmark_report_should_include_case_names():

    report = {
        "cases": {
            "python_tool_calling": {
                "metrics": {
                    1: {
                        "f1_at_k": 0.67,
                    }
                }
            },
            "agent_memory": {
                "metrics": {
                    1: {
                        "f1_at_k": 1.0,
                    }
                }
            },
        },
        "average_f1_by_k": {
            1: 0.835,
        },
    }

    output = format_benchmark_report(report)

    assert "python_tool_calling" in output
    assert "agent_memory" in output


def test_format_benchmark_report_should_include_efficiency_metrics():

    report = {
        "cases": {},
        "average_f1_by_k": {
            1: 1.0,
        },
        "average_retrieved_count_by_k": {
            1: 1.0,
        },
        "average_compression_ratio_by_k": {
            1: 0.5,
        },
    }

    output = format_benchmark_report(
        report,
    )

    assert "Average Retrieved Count" in output
    assert "Average Compression Ratio" in output


def test_format_benchmark_report_should_include_score_gap():
    report = {
        "cases": {
            "test_case": {
                "metrics": {
                    3: {
                        "f1_at_k": 1.0,
                        "retrieved_count": 1,
                        "compression_ratio": 2 / 3,
                        "score_gap": 0.75,
                    },
                },
            },
        },
        "average_f1_by_k": {
            3: 1.0,
        },
        "average_retrieved_count_by_k": {
            3: 1.0,
        },
        "average_compression_ratio_by_k": {
            3: 2 / 3,
        },
    }

    output = format_benchmark_report(report)

    assert "Gap: 0.75" in output


def test_format_benchmark_report_should_include_top_score_diagnostics():
    report = {
        "cases": {
            "test_case": {
                "metrics": {
                    3: {
                        "f1_at_k": 1.0,
                        "retrieved_count": 1,
                        "compression_ratio": 2 / 3,
                        "score_gap": 0.75,
                        "top_memory_key": "memory:top",
                        "top_score": 1.0,
                        "second_memory_key": "memory:second",
                        "second_score": 0.25,
                    },
                },
            },
        },
        "average_f1_by_k": {
            3: 1.0,
        },
        "average_retrieved_count_by_k": {
            3: 1.0,
        },
        "average_compression_ratio_by_k": {
            3: 2 / 3,
        },
    }

    output = format_benchmark_report(report)

    assert "Top: memory:top (1.00)" in output
    assert "Second: memory:second (0.25)" in output
