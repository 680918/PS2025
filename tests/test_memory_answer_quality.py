import pytest

from memory.memory_answer_quality import (
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
