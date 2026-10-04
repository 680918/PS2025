from memory.relevance_ranker import score_memory


def calculate_pairwise_order_accuracy(
    scored_items,
):
    correct_pairs = 0
    comparable_pairs = 0

    for index, left in enumerate(scored_items):
        for right in scored_items[index + 1 :]:
            left_relevance = left["relevance"]
            right_relevance = right["relevance"]

            if left_relevance == right_relevance:
                continue

            comparable_pairs += 1

            if left_relevance > right_relevance:
                higher = left
                lower = right
            else:
                higher = right
                lower = left

            if higher["score"] > lower["score"]:
                correct_pairs += 1

    if comparable_pairs == 0:
        return 0.0

    return correct_pairs / comparable_pairs


def evaluate_calibration_case(
    query,
    items,
):
    scored_items = []

    for item in items:
        score = score_memory(
            item,
            query=query,
        )

        scored_items.append(
            {
                **item,
                "score": score,
            }
        )

    pairwise_order_accuracy = calculate_pairwise_order_accuracy(
        scored_items,
    )

    return {
        "scored_items": scored_items,
        "pairwise_order_accuracy": (pairwise_order_accuracy),
    }


def evaluate_calibration_dataset(
    cases,
):
    case_results = []

    for case in cases:
        result = evaluate_calibration_case(
            query=case["query"],
            items=case["items"],
        )

        case_results.append(
            {
                "name": case["name"],
                **result,
            }
        )

    if not case_results:
        return {
            "cases": [],
            "average_pairwise_order_accuracy": 0.0,
        }

    average_pairwise_order_accuracy = sum(
        case["pairwise_order_accuracy"] for case in case_results
    ) / len(case_results)

    return {
        "cases": case_results,
        "average_pairwise_order_accuracy": (average_pairwise_order_accuracy),
    }
