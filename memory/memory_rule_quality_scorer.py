from memory.memory_answer_quality import (
    validate_answer_quality_score,
)


def validate_rule_scoring_spec(
    rules,
):
    for field_name in (
        "required_phrases",
        "forbidden_phrases",
    ):
        phrases = rules.get(field_name)

        if not isinstance(
            phrases,
            list,
        ):
            raise ValueError(f"{field_name} must be a list")

        if not all(isinstance(phrase, str) and phrase.strip() for phrase in phrases):
            raise ValueError(f"{field_name} must contain non-empty strings")

    return True


def _calculate_phrase_coverage(
    answer,
    phrases,
):
    if not phrases:
        return 0.0

    normalized_answer = answer.lower()

    matched = sum(1 for phrase in phrases if phrase.lower() in normalized_answer)

    return matched / len(phrases)


def score_answer_with_rules(
    answer,
    rules,
):
    validate_rule_scoring_spec(rules)

    required_coverage = _calculate_phrase_coverage(
        answer,
        rules["required_phrases"],
    )

    forbidden_coverage = _calculate_phrase_coverage(
        answer,
        rules["forbidden_phrases"],
    )

    score = 0.5 + (0.5 * required_coverage) - (0.75 * forbidden_coverage)

    score = max(
        0.0,
        min(
            1.0,
            score,
        ),
    )

    return validate_answer_quality_score(score)
