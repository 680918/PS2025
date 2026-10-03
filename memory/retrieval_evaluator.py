from memory.relevance_ranker import (
    calculate_score_gap,
    rank_memories,
    get_top_score_diagnostics,
)


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
    threshold=None,
):
    ranked_memories = rank_memories(
        memories,
        query=query,
        top_k=top_k,
        threshold=threshold,
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
    threshold=None,
    score_gap_threshold=None,
):
    ranked_memories = rank_memories(
        memories,
        query=query,
        top_k=top_k,
        threshold=threshold,
        score_gap_threshold=score_gap_threshold,
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

    precision = calculate_precision_at_k(
        retrieved_keys,
        relevant_keys,
    )

    f1 = calculate_f1(
        precision,
        recall,
    )

    score_gap = calculate_score_gap(
        memories,
        query=query,
    )

    diagnostics = get_top_score_diagnostics(
        memories,
        query=query,
    )

    if top_k:
        compression_ratio = 1 - len(retrieved_keys) / top_k
    else:
        compression_ratio = 0.0

    return {
        "recall_at_k": recall,
        "precision_at_k": precision,
        "f1_at_k": f1,
        "score_gap": score_gap,
        "retrieved_count": len(retrieved_keys),
        "compression_ratio": compression_ratio,
        "top_memory_key": diagnostics["top_memory_key"],
        "top_score": diagnostics["top_score"],
        "second_memory_key": diagnostics["second_memory_key"],
        "second_score": diagnostics["second_score"],
    }


def evaluate_retrieval_quality_by_k(
    memories,
    query,
    relevant_keys,
    k_values,
    threshold=None,
    score_gap_threshold=None,
):
    results = {}

    for k in k_values:
        results[k] = evaluate_retrieval_quality(
            memories,
            query=query,
            relevant_keys=relevant_keys,
            top_k=k,
            threshold=threshold,
            score_gap_threshold=score_gap_threshold,
        )

    return results


def calculate_f1(
    precision,
    recall,
):
    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)
