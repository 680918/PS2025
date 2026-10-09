import pytest

from memory.memory_llm_pairwise_judge import (
    judge_memory_contribution_pair,
)


def test_pairwise_judge_should_return_effect_and_reason():
    captured = {}

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        captured["system_prompt"] = system_prompt
        captured["user_message"] = user_message

        return {
            "status": "success",
            "content": (
                '{"effect": "neutral", "reason": "两个回答的核心技术内容基本相同。"}'
            ),
        }

    result = judge_memory_contribution_pair(
        query="How should I design a database?",
        without_memory_answer=(
            "Design around entities, relationships, and access patterns."
        ),
        with_memory_answer=(
            "Design around entities, "
            "relationships, and access patterns "
            "while considering stakeholders."
        ),
        evaluation_criteria=[
            ("Give technically sound database design guidance."),
        ],
        llm_call=fake_llm_call,
    )

    assert result == {
        "effect": "neutral",
        "reason": ("两个回答的核心技术内容基本相同。"),
    }

    assert "直接比较两个回答" in captured["system_prompt"]

    assert "轻微的措辞、风格或表达方式变化" in captured["system_prompt"]

    assert "How should I design a database?" in captured["user_message"]

    assert "while considering stakeholders" in captured["user_message"]


def test_pairwise_judge_should_reject_invalid_effect():
    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "success",
            "content": ('{"effect": "better", "reason": "回答有所改善。"}'),
        }

    with pytest.raises(
        ValueError,
        match="invalid effect",
    ):
        judge_memory_contribution_pair(
            query="Explain Python.",
            without_memory_answer="Answer A.",
            with_memory_answer="Answer B.",
            evaluation_criteria=[
                "Explain accurately.",
            ],
            llm_call=fake_llm_call,
        )


def test_pairwise_judge_should_reject_empty_reason():
    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "success",
            "content": ('{"effect": "neutral", "reason": ""}'),
        }

    with pytest.raises(
        ValueError,
        match="reason",
    ):
        judge_memory_contribution_pair(
            query="Explain Python.",
            without_memory_answer="Answer A.",
            with_memory_answer="Answer B.",
            evaluation_criteria=[
                "Explain accurately.",
            ],
            llm_call=fake_llm_call,
        )


def test_pairwise_judge_should_surface_llm_error():
    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "error",
            "error_type": "api_error",
            "retryable": False,
        }

    with pytest.raises(
        RuntimeError,
        match="Pairwise Judge LLM call failed",
    ):
        judge_memory_contribution_pair(
            query="Explain Python.",
            without_memory_answer="Answer A.",
            with_memory_answer="Answer B.",
            evaluation_criteria=[
                "Explain accurately.",
            ],
            llm_call=fake_llm_call,
        )


def test_pairwise_judge_should_include_reference_context():
    captured = {}

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        captured["system_prompt"] = system_prompt
        captured["user_message"] = user_message

        return {
            "status": "success",
            "content": (
                '{"effect": "negative", '
                '"reason": '
                '"回答依赖了与权威事实冲突的错误记忆。"}'
            ),
        }

    result = judge_memory_contribution_pair(
        query="Continue learning Python",
        without_memory_answer=("Continue Python practice."),
        with_memory_answer=(
            "You fully mastered Python, so skip foundational practice."
        ),
        evaluation_criteria=[
            ("Preserve useful practice when learning is incomplete."),
        ],
        reference_context=[
            (
                "The learner has not fully "
                "mastered Python and still "
                "needs foundational practice."
            ),
        ],
        llm_call=fake_llm_call,
    )

    assert result["effect"] == "negative"

    assert "权威评估事实" in captured["user_message"]

    assert "The learner has not fully mastered Python" in captured["user_message"]
