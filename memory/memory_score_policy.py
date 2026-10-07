RELEVANCE_GAP_THRESHOLD = 0.08
FLOAT_TOLERANCE = 1e-9


def should_protect_relevance(
    higher_relevance_score,
    lower_relevance_score,
):
    relevance_gap = higher_relevance_score - lower_relevance_score

    return relevance_gap + FLOAT_TOLERANCE >= RELEVANCE_GAP_THRESHOLD


def rank_scored_memories_with_relevance_guard(
    scored_items,
):
    if not scored_items:
        return []

    highest_relevance_score = max(item["relevance_score"] for item in scored_items)

    def ranking_key(item):
        relevance_gap = highest_relevance_score - item["relevance_score"]

        relevance_band = int(
            (relevance_gap + FLOAT_TOLERANCE) / RELEVANCE_GAP_THRESHOLD
        )

        return (
            relevance_band,
            -item["composite_score"],
            -item["relevance_score"],
        )

    return sorted(
        scored_items,
        key=ranking_key,
    )
