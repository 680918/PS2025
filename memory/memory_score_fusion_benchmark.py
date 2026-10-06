from memory.memory_score_fusion_evaluator import (
    evaluate_memory_score_fusion_items,
)


def get_memory_score_fusion_benchmark_cases():
    return [
        {
            "name": "relevance_should_dominate_high_quality_distractor",
            "items": [
                {
                    "memory_key": "relevant-lower-quality",
                    "expected_rank": 1,
                    "relevance_score": 0.9,
                    "importance": 0.2,
                    "confidence": 0.2,
                },
                {
                    "memory_key": "unrelated-high-quality",
                    "expected_rank": 2,
                    "relevance_score": 0.1,
                    "importance": 1.0,
                    "confidence": 1.0,
                },
            ],
        },
        {
            "name": "quality_should_break_relevance_tie",
            "items": [
                {
                    "memory_key": "high-quality",
                    "expected_rank": 1,
                    "relevance_score": 0.8,
                    "importance": 0.9,
                    "confidence": 0.9,
                },
                {
                    "memory_key": "low-quality",
                    "expected_rank": 2,
                    "relevance_score": 0.8,
                    "importance": 0.2,
                    "confidence": 0.2,
                },
            ],
        },
    ]


def run_memory_score_fusion_benchmark():
    results = []

    for case in get_memory_score_fusion_benchmark_cases():
        evaluation = evaluate_memory_score_fusion_items(
            case["items"],
        )

        results.append(
            {
                "name": case["name"],
                **evaluation,
            }
        )

    return results


def summarize_memory_score_fusion_benchmark(
    results,
):
    if not results:
        return {
            "overall_pairwise_order_accuracy": 0.0,
            "minimum_pairwise_margin": 0.0,
            "average_minimum_pairwise_margin": 0.0,
        }

    accuracies = [result["pairwise_order_accuracy"] for result in results]

    margins = [result["minimum_pairwise_margin"] for result in results]

    return {
        "overall_pairwise_order_accuracy": (sum(accuracies) / len(accuracies)),
        "minimum_pairwise_margin": min(margins),
        "average_minimum_pairwise_margin": (sum(margins) / len(margins)),
    }
