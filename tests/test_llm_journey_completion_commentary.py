import pytest
from learning.llm_journey_completion_commentary import (
    LLMJourneyCompletionCommentary,
)


def test_llm_completion_commentary_should_generate_text_from_summary():
    calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(
            {
                "system_prompt": system_prompt,
                "user_message": user_message,
            }
        )

        return {
            "status": "success",
            "content": "你完成了本阶段学习，理解度从60提升到85，学习趋势持续改善。",
        }

    generator = LLMJourneyCompletionCommentary(
        llm_call=fake_call_llm,
    )

    summary = {
        "journey_id": "journey_001",
        "domain": "Python",
        "goal": "能够独立编写简单程序",
        "status": "completed",
        "completed_sessions": 2,
        "first_understanding": 60,
        "latest_understanding": 85,
        "understanding_change": 25,
        "trend": "improving",
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    commentary = generator.generate(summary)

    assert commentary == ("你完成了本阶段学习，理解度从60提升到85，学习趋势持续改善。")

    assert len(calls) == 1

    user_message = calls[0]["user_message"]

    assert "Python" in user_message
    assert "能够独立编写简单程序" in user_message
    assert "60" in user_message
    assert "85" in user_message
    assert "25" in user_message
    assert "2" in user_message


def test_llm_completion_commentary_should_reject_llm_error_response():
    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "request timed out",
            "content": None,
        }

    generator = LLMJourneyCompletionCommentary(
        llm_call=fake_call_llm,
    )

    summary = {
        "domain": "Python",
        "goal": "能够独立编写简单程序",
        "completed_sessions": 2,
        "first_understanding": 60,
        "latest_understanding": 85,
        "understanding_change": 25,
        "trend": "improving",
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    with pytest.raises(
        RuntimeError,
        match="LLM journey completion commentary generation failed",
    ):
        generator.generate(summary)


def test_llm_completion_commentary_should_reject_empty_content():
    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "success",
            "content": "",
        }

    generator = LLMJourneyCompletionCommentary(
        llm_call=fake_call_llm,
    )

    summary = {
        "journey_id": "journey_001",
        "domain": "Python",
        "goal": "能够独立编写简单程序",
        "status": "completed",
        "completed_sessions": 2,
        "first_understanding": 60,
        "latest_understanding": 85,
        "understanding_change": 25,
        "trend": "improving",
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    with pytest.raises(
        RuntimeError,
        match="LLM journey completion commentary is empty",
    ):
        generator.generate(summary)
