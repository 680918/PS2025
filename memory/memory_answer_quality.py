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


def normalize_answer_quality_evaluation(
    evaluation,
):
    if isinstance(
        evaluation,
        dict,
    ):
        if "score" not in evaluation:
            raise ValueError("answer quality evaluation must include score")

        score = validate_answer_quality_score(evaluation["score"])

        reason = evaluation.get("reason")

        if reason is not None:
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("answer quality reason must be a non-empty string")

            reason = reason.strip()

        return {
            "score": score,
            "reason": reason,
        }

    score = validate_answer_quality_score(evaluation)

    return {
        "score": score,
        "reason": None,
    }
