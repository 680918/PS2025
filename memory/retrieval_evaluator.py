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


def calculate_precision_at_k(
    retrieved_keys,
    relevant_keys,
):
    retrieved_keys = set(retrieved_keys)

    if not retrieved_keys:
        return 0.0

    relevant_keys = set(relevant_keys)

    hits = len(retrieved_keys & relevant_keys)

    return hits / len(retrieved_keys)


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


def evaluate_retrieval_quality(
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

    recall = calculate_recall_at_k(
        retrieved_keys,
        relevant_keys,
    )

    precision = calculate_precision_at_k(
        retrieved_keys,
        relevant_keys,
    )

    f1 = calculate_f1(
        precision,
        recall,
    )

    return {
        "recall_at_k": recall,
        "precision_at_k": precision,
        "f1_at_k": f1,
    }


def evaluate_retrieval_quality_by_k(
    memories,
    query,
    relevant_keys,
    k_values,
):
    results = {}

    for k in k_values:
        results[k] = evaluate_retrieval_quality(
            memories,
            query=query,
            relevant_keys=relevant_keys,
            top_k=k,
        )

    return results


def calculate_f1(
    precision,
    recall,
):
    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)
