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
