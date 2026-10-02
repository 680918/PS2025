from memory.retrieval_benchmark_runner import (
    run_retrieval_benchmark,
)

from memory.retrieval_benchmark_report import (
    summarize_benchmark_results,
)


def test_run_retrieval_benchmark_should_generate_baseline():

    results = run_retrieval_benchmark(
        k_values=[1, 2, 3],
    )

    report = summarize_benchmark_results(results)

    assert "average_f1_by_k" in report

    assert 1 in report["average_f1_by_k"]
    assert 2 in report["average_f1_by_k"]
    assert 3 in report["average_f1_by_k"]


def test_run_retrieval_benchmark_should_support_threshold():

    from memory.retrieval_benchmark_runner import (
        run_retrieval_benchmark,
    )

    results = run_retrieval_benchmark(
        k_values=[1, 2, 3],
        threshold=0.5,
    )

    assert results
    assert "metrics" in results[0]
