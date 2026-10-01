from memory.retrieval_benchmark import (
    get_retrieval_benchmark_cases,
)
from memory.retrieval_benchmark_runner import (
    run_retrieval_benchmark,
)


def test_retrieval_benchmark_should_have_cases():

    cases = get_retrieval_benchmark_cases()

    assert len(cases) > 0


def test_retrieval_benchmark_case_should_have_required_fields():

    cases = get_retrieval_benchmark_cases()

    case = cases[0]

    assert "name" in case
    assert "query" in case
    assert "memories" in case
    assert "relevant_keys" in case


def test_retrieval_benchmark_runner_should_return_results():

    results = run_retrieval_benchmark(
        k_values=[1, 2],
    )

    assert len(results) > 0


def test_retrieval_benchmark_result_should_include_metrics():

    results = run_retrieval_benchmark(
        k_values=[1, 2],
    )

    first_case = results[0]

    assert "name" in first_case
    assert "metrics" in first_case

    assert 1 in first_case["metrics"]
    assert 2 in first_case["metrics"]
