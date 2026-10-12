from learning.llm_learning_feedback_extractor import (
    LLMLearningFeedbackExtractor,
)


def test_extract_should_return_explicit_learning_feedback():
    captured = {}

    def fake_llm_call(system_prompt, user_message):
        captured["system_prompt"] = system_prompt
        captured["user_message"] = user_message

        return {
            "status": "success",
            "content": """
{
    "feedback": {
        "understanding_score": 80,
        "difficulty": "还不清楚 Memory 怎么接入",
        "next_step": "实现 Tool Calling 与 Memory 的最小 Demo"
    }
}
""",
        }

    extractor = LLMLearningFeedbackExtractor(
        llm_call=fake_llm_call,
    )

    result = extractor.extract(
        "Tool Calling 我大概理解到 80 分，"
        "现在还不清楚 Memory 怎么接入，"
        "下一步想做一个最小 Demo。"
    )

    assert result == {
        "understanding_score": 80,
        "difficulty": "还不清楚 Memory 怎么接入",
        "next_step": "实现 Tool Calling 与 Memory 的最小 Demo",
    }

    assert "80" in captured["user_message"]
    assert "Memory" in captured["user_message"]


def test_extract_should_return_none_when_feedback_is_incomplete():
    def fake_llm_call(system_prompt, user_message):
        return {
            "status": "success",
            "content": """
{
    "feedback": {
        "understanding_score": 80,
        "difficulty": "还不清楚 Memory 怎么接入"
    }
}
""",
        }

    extractor = LLMLearningFeedbackExtractor(
        llm_call=fake_llm_call,
    )

    result = extractor.extract(
        "Tool Calling 我大概理解到 80 分，但还不清楚 Memory 怎么接入。"
    )

    assert result is None


def test_extract_should_allow_no_feedback_for_normal_conversation():
    captured = {}

    def fake_llm_call(system_prompt, user_message):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": """
{
    "feedback": null
}
""",
        }

    extractor = LLMLearningFeedbackExtractor(
        llm_call=fake_llm_call,
    )

    result = extractor.extract("Tool Calling 和普通函数调用有什么区别？")

    assert result is None

    assert '"feedback": null' in captured["system_prompt"]
