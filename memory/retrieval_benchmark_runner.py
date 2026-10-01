from memory.retrieval_benchmark import (
    get_retrieval_benchmark_cases,
)

from memory.retrieval_evaluator import (
    evaluate_retrieval_quality_by_k,
)


def run_retrieval_benchmark(
    k_values,
):
    cases = get_retrieval_benchmark_cases()

    results = []

    for case in cases:
        metrics = evaluate_retrieval_quality_by_k(
            case["memories"],
            query=case["query"],
            relevant_keys=case["relevant_keys"],
            k_values=k_values,
        )

        results.append(
            {
                "name": case["name"],
                "metrics": metrics,
            }
        )

    return results
