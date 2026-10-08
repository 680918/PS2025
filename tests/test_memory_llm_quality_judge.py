import pytest

from memory.memory_llm_quality_judge import (
    score_answer_with_llm,
)


def test_llm_quality_judge_should_return_normalized_score_and_reason():
    captured = {}

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        captured["system_prompt"] = system_prompt
        captured["user_message"] = user_message

        return {
            "status": "success",
            "content": ('{"score": 0.85, "reason": "The answer meets the criteria."}'),
        }

    result = score_answer_with_llm(
        query="Continue learning Tool Calling",
        answer="Let's build a practical tool call.",
        evaluation_criteria=[
            "Continue from existing understanding.",
            "Move toward practical execution.",
        ],
        llm_call=fake_llm_call,
    )

    assert result["score"] == pytest.approx(0.85)

    assert result["reason"] == ("The answer meets the criteria.")

    assert "0 and 1" in captured["system_prompt"]

    assert "Continue learning Tool Calling" in (captured["user_message"])

    assert "practical tool call" in (captured["user_message"])


def test_llm_quality_judge_should_reject_invalid_json():
    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "success",
            "content": "not json",
        }

    with pytest.raises(
        ValueError,
        match="invalid judge response",
    ):
        score_answer_with_llm(
            query="query",
            answer="answer",
            evaluation_criteria=["criterion"],
            llm_call=fake_llm_call,
        )


def test_llm_quality_judge_should_reject_invalid_score():
    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "success",
            "content": ('{"score": 1.5, "reason": "invalid score"}'),
        }

    with pytest.raises(
        ValueError,
        match="answer quality score",
    ):
        score_answer_with_llm(
            query="query",
            answer="answer",
            evaluation_criteria=["criterion"],
            llm_call=fake_llm_call,
        )


def test_llm_quality_judge_should_surface_llm_error():
    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
        }

    with pytest.raises(
        RuntimeError,
        match="llm_timeout",
    ):
        score_answer_with_llm(
            query="query",
            answer="answer",
            evaluation_criteria=["criterion"],
            llm_call=fake_llm_call,
        )
