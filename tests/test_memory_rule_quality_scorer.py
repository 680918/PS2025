import pytest

from memory.memory_rule_quality_scorer import (
    score_answer_with_rules,
    validate_rule_scoring_spec,
)


def test_rule_quality_scorer_should_reward_required_phrases():
    rules = {
        "required_phrases": [
            "practical",
            "tool",
        ],
        "forbidden_phrases": [
            "start from zero",
        ],
    }

    score = score_answer_with_rules(
        "Let's build a practical tool workflow.",
        rules,
    )

    assert score == pytest.approx(1.0)


def test_rule_quality_scorer_should_penalize_forbidden_phrases():
    rules = {
        "required_phrases": [
            "practice",
        ],
        "forbidden_phrases": [
            "fully mastered",
            "skip all further practice",
        ],
    }

    score = score_answer_with_rules(
        ("You have fully mastered this topic and should skip all further practice."),
        rules,
    )

    assert score < 0.5


def test_rule_quality_scorer_should_return_neutral_baseline_without_matches():
    rules = {
        "required_phrases": [
            "practical",
        ],
        "forbidden_phrases": [
            "start from zero",
        ],
    }

    score = score_answer_with_rules(
        "Tool Calling is a model capability.",
        rules,
    )

    assert score == pytest.approx(0.5)


def test_rule_scoring_spec_should_reject_invalid_phrase_lists():
    rules = {
        "required_phrases": "practical",
        "forbidden_phrases": [],
    }

    with pytest.raises(
        ValueError,
        match="required_phrases must be a list",
    ):
        validate_rule_scoring_spec(rules)
