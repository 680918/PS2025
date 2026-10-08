def validate_answer_quality_score(
    score,
):
    if (
        isinstance(score, bool)
        or not isinstance(
            score,
            (int, float),
        )
        or score < 0.0
        or score > 1.0
    ):
        raise ValueError("answer quality score must be a number between 0 and 1")

    return score
