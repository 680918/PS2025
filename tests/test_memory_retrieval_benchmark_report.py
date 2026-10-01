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
