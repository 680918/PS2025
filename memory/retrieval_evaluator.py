from memory.relevance_ranker import rank_memories


def calculate_recall_at_k(
    retrieved_keys,
    relevant_keys,
):
    relevant_keys = set(relevant_keys)

    if not relevant_keys:
        return 0.0

    retrieved_keys = set(retrieved_keys)

    hits = len(retrieved_keys & relevant_keys)

    return hits / len(relevant_keys)


def evaluate_retrieval_recall(
    memories,
    query,
    relevant_keys,
    top_k,
):
    ranked_memories = rank_memories(
        memories,
        query=query,
        top_k=top_k,
    )

    retrieved_keys = [memory.get("memory_key") for memory in ranked_memories]

    return calculate_recall_at_k(
        retrieved_keys,
        relevant_keys,
    )
