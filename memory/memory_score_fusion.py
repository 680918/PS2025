from memory.relevance_ranker import score_memory

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
    scored_memories = []

    for memory in memories:
        relevance_score = score_memory(
            memory,
            query,
        )

        composite_score = calculate_memory_score(
            memory,
            relevance_score=relevance_score,
        )

        scored_memories.append(
            (
                memory,
                composite_score,
            )
        )

    scored_memories.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    return [memory for memory, _ in scored_memories]
