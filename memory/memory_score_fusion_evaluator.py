from memory.memory_score_fusion import calculate_memory_score


def calculate_pairwise_order_accuracy(
    scored_items,
):
    correct = 0
    total = 0

    for index, left in enumerate(scored_items):
        for right in scored_items[index + 1 :]:
            if left["expected_rank"] == right["expected_rank"]:
                continue

            total += 1

            if left["expected_rank"] < right["expected_rank"]:
                higher = left
                lower = right
            else:
                higher = right
                lower = left

            if higher["score"] > lower["score"]:
                correct += 1

    if total == 0:
        return 0.0

    return correct / total


def calculate_minimum_pairwise_margin(
    scored_items,
):
    margins = []

    for index, left in enumerate(scored_items):
        for right in scored_items[index + 1 :]:
            if left["expected_rank"] == right["expected_rank"]:
                continue

            if left["expected_rank"] < right["expected_rank"]:
                higher = left
                lower = right
            else:
                higher = right
                lower = left

            margins.append(higher["score"] - lower["score"])

    if not margins:
        return 0.0

    return min(margins)


def evaluate_memory_score_fusion(
    scored_items,
):
    return {
        "pairwise_order_accuracy": (
            calculate_pairwise_order_accuracy(
                scored_items,
            )
        ),
        "minimum_pairwise_margin": (
            calculate_minimum_pairwise_margin(
                scored_items,
            )
        ),
    }


def score_memory_fusion_items(
    items,
):
    scored_items = []

    for item in items:
        score = calculate_memory_score(
            item,
            relevance_score=item["relevance_score"],
        )

        scored_items.append(
            {
                **item,
                "score": score,
            }
        )

    return scored_items


def evaluate_memory_score_fusion_items(
    items,
):
    scored_items = score_memory_fusion_items(
        items,
    )

    return evaluate_memory_score_fusion(
        scored_items,
    )
