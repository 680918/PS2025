import math


def calculate_delta_correlation(
    first,
    second,
):
    if not first or not second:
        return 0.0

    if len(first) != len(second):
        raise ValueError("lists must have same length")

    n = len(first)

    mean_first = sum(first) / n
    mean_second = sum(second) / n

    numerator = sum(
        (a - mean_first) * (b - mean_second)
        for a, b in zip(
            first,
            second,
        )
    )

    denominator_first = math.sqrt(sum((a - mean_first) ** 2 for a in first))

    denominator_second = math.sqrt(sum((b - mean_second) ** 2 for b in second))

    if denominator_first == 0 or denominator_second == 0:
        return 0.0

    return numerator / (denominator_first * denominator_second)


def calculate_score_scale_gap(
    first,
    second,
):
    if not first or not second:
        return 0.0

    if len(first) != len(second):
        raise ValueError("lists must have same length")

    return abs((sum(first) / len(first)) - (sum(second) / len(second)))


def calculate_score_bias(
    rule_scores,
    llm_scores,
):
    if not rule_scores or not llm_scores:
        return 0.0

    if len(rule_scores) != len(llm_scores):
        raise ValueError("lists must have same length")

    rule_mean = sum(rule_scores) / len(rule_scores)

    llm_mean = sum(llm_scores) / len(llm_scores)

    return llm_mean - rule_mean
