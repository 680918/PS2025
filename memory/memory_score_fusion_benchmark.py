from memory.memory_score_policy import (
    rank_scored_memories_with_relevance_guard,
)
from memory.memory_score_fusion_evaluator import (
    evaluate_memory_score_fusion,
    evaluate_memory_score_fusion_items,
    score_memory_fusion_items,
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


def get_memory_score_fusion_hard_cases():
    return [
        {
            "name": "close_relevance_quality_conflict",
            "items": [
                {
                    "memory_key": "more-relevant-lower-quality",
                    "expected_rank": 1,
                    "relevance_score": 0.75,
                    "importance": 0.2,
                    "confidence": 0.2,
                },
                {
                    "memory_key": "less-relevant-higher-quality",
                    "expected_rank": 2,
                    "relevance_score": 0.65,
                    "importance": 1.0,
                    "confidence": 1.0,
                },
            ],
        },
        {
            "name": "small_relevance_gap_quality_tie_break",
            "items": [
                {
                    "memory_key": "slightly-more-relevant-lower-quality",
                    "expected_rank": 2,
                    "relevance_score": 0.70,
                    "importance": 0.2,
                    "confidence": 0.2,
                },
                {
                    "memory_key": "slightly-less-relevant-higher-quality",
                    "expected_rank": 1,
                    "relevance_score": 0.68,
                    "importance": 0.9,
                    "confidence": 0.9,
                },
            ],
        },
        {
            "name": "relevance_gap_boundary_005",
            "items": [
                {
                    "memory_key": "relevance-wins-boundary",
                    "expected_rank": 1,
                    "relevance_score": 0.70,
                    "importance": 0.2,
                    "confidence": 0.2,
                },
                {
                    "memory_key": "quality-wins-boundary",
                    "expected_rank": 2,
                    "relevance_score": 0.65,
                    "importance": 0.9,
                    "confidence": 0.9,
                },
            ],
        },
        {
            "name": "relevance_gap_guard_threshold",
            "items": [
                {
                    "memory_key": "more-relevant-at-threshold",
                    "expected_rank": 1,
                    "relevance_score": 0.70,
                    "importance": 0.2,
                    "confidence": 0.2,
                },
                {
                    "memory_key": "higher-quality-at-threshold",
                    "expected_rank": 2,
                    "relevance_score": 0.62,
                    "importance": 0.9,
                    "confidence": 0.9,
                },
            ],
        },
    ]


def run_memory_score_fusion_hard_cases():
    results = []

    for case in get_memory_score_fusion_hard_cases():
        evaluation = _evaluate_memory_score_fusion_hard_case(
            case["items"],
        )

        results.append(
            {
                "name": case["name"],
                **evaluation,
            }
        )

    return results


def summarize_memory_score_fusion_hard_cases(
    results,
):
    if not results:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "failed_cases": 0,
            "weakest_case": None,
        }

    passed_cases = [
        result for result in results if result["pairwise_order_accuracy"] == 1.0
    ]

    failed_cases = [
        result for result in results if result["pairwise_order_accuracy"] < 1.0
    ]

    weakest_case = min(
        results,
        key=lambda result: result["minimum_pairwise_margin"],
    )

    return {
        "total_cases": len(results),
        "passed_cases": len(passed_cases),
        "failed_cases": len(failed_cases),
        "weakest_case": weakest_case["name"],
    }


def _evaluate_memory_score_fusion_hard_case(
    items,
):
    scored_items = score_memory_fusion_items(
        items,
    )

    policy_items = [
        {
            **item,
            "composite_score": item["score"],
        }
        for item in scored_items
    ]

    ranked_items = rank_scored_memories_with_relevance_guard(
        policy_items,
    )

    correct = 0
    total = 0

    for index, left in enumerate(ranked_items):
        for right in ranked_items[index + 1 :]:
            if left["expected_rank"] == right["expected_rank"]:
                continue

            total += 1

            if left["expected_rank"] < right["expected_rank"]:
                correct += 1

    accuracy = correct / total if total else 0.0

    raw_evaluation = evaluate_memory_score_fusion(
        scored_items,
    )

    return {
        "pairwise_order_accuracy": accuracy,
        "minimum_pairwise_margin": raw_evaluation["minimum_pairwise_margin"],
    }
