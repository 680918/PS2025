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


def test_retrieval_benchmark_should_include_multiple_domains():

    cases = get_retrieval_benchmark_cases()

    names = [case["name"] for case in cases]

    assert len(cases) >= 4

    assert "python_tool_calling" in names
    assert "agent_memory" in names
    assert "stock_strategy" in names
    assert "reading_system" in names


def test_retrieval_benchmark_should_include_hard_cases():

    cases = get_retrieval_benchmark_cases()

    names = [case["name"] for case in cases]

    assert "agent_memory_semantic_hard" in names


def test_retrieval_benchmark_should_include_keyword_distractor_cases():

    cases = get_retrieval_benchmark_cases()

    names = [case["name"] for case in cases]

    assert "tool_calling_keyword_distractor" in names


def test_retrieval_benchmark_should_include_memory_overload_case():

    cases = get_retrieval_benchmark_cases()

    names = [case["name"] for case in cases]

    assert "memory_overload" in names


def test_benchmark_should_support_retrieval_threshold():

    from memory.retrieval_benchmark_runner import (
        run_retrieval_benchmark,
    )

    results = run_retrieval_benchmark(
        k_values=[1, 2, 3],
        threshold=0.5,
    )

    assert results
    assert "metrics" in results[0]
