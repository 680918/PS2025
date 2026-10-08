import pytest

from memory.memory_answer_quality import (
    normalize_answer_quality_evaluation,
    validate_answer_quality_score,
)


@pytest.mark.parametrize(
    "score",
    [
        0.0,
        0.5,
        1.0,
    ],
)
def test_answer_quality_score_should_accept_normalized_values(
    score,
):
    assert validate_answer_quality_score(score) == score


@pytest.mark.parametrize(
    "score",
    [
        -0.01,
        1.01,
        "0.8",
        None,
    ],
)
def test_answer_quality_score_should_reject_invalid_values(
    score,
):
    with pytest.raises(
        ValueError,
        match="answer quality score",
    ):
        validate_answer_quality_score(score)


def test_answer_quality_evaluation_should_normalize_numeric_score():
    result = normalize_answer_quality_evaluation(0.80)

    assert result == {
        "score": 0.80,
        "reason": None,
    }


def test_answer_quality_evaluation_should_preserve_reason():
    result = normalize_answer_quality_evaluation(
        {
            "score": 0.85,
            "reason": ("The answer satisfies the criteria."),
        }
    )

    assert result == {
        "score": 0.85,
        "reason": ("The answer satisfies the criteria."),
    }


def test_answer_quality_evaluation_should_reject_invalid_reason():
    with pytest.raises(
        ValueError,
        match="answer quality reason",
    ):
        normalize_answer_quality_evaluation(
            {
                "score": 0.80,
                "reason": "",
            }
        )
