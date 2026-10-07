from memory.relevance_ranker import score_memory
from memory.memory_score_policy import (
    rank_scored_memories_with_relevance_guard,
)


RELEVANCE_WEIGHT = 0.60
IMPORTANCE_WEIGHT = 0.25
CONFIDENCE_WEIGHT = 0.15


def calculate_memory_score(
    memory,
    relevance_score,
):
    importance = memory.get("importance", 0.0)
    confidence = memory.get("confidence", 0.0)

    return (
        relevance_score * RELEVANCE_WEIGHT
        + importance * IMPORTANCE_WEIGHT
        + confidence * CONFIDENCE_WEIGHT
    )


def rank_memories_by_composite_score(
    memories,
    query=None,
):
    scored_items = []

    for memory in memories:
        relevance_score = score_memory(
            memory,
            query,
        )

        composite_score = calculate_memory_score(
            memory,
            relevance_score=relevance_score,
        )

        scored_items.append(
            {
                "memory": memory,
                "relevance_score": relevance_score,
                "composite_score": composite_score,
            }
        )

    ranked_items = rank_scored_memories_with_relevance_guard(
        scored_items,
    )

    return [item["memory"] for item in ranked_items]
