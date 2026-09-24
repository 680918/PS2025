import pytest
from learning.llm_curriculum_generator import (
    LLMCurriculumGenerator,
)


def test_llm_curriculum_generator_should_return_topics_from_llm_response():
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
            "content": """
            {
                "curriculum_topics": [
                    "Python变量",
                    "Python条件判断",
                    "Python函数"
                ]
            }
            """,
        }

    generator = LLMCurriculumGenerator(
        llm_call=fake_call_llm,
    )

    topics = generator.generate(
        domain="Python",
        goal="能够独立编写简单程序",
    )

    assert topics == [
        "Python变量",
        "Python条件判断",
        "Python函数",
    ]

    assert len(calls) == 1

    assert "Python" in calls[0]["user_message"]
    assert "能够独立编写简单程序" in calls[0]["user_message"]


def test_llm_curriculum_generator_should_reject_llm_error_response():
    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "request timed out",
            "content": None,
        }

    generator = LLMCurriculumGenerator(
        llm_call=fake_call_llm,
    )

    with pytest.raises(
        RuntimeError,
        match="LLM curriculum generation failed",
    ):
        generator.generate(
            domain="Python",
            goal="能够独立编写简单程序",
        )


def test_llm_curriculum_generator_should_reject_invalid_json_response():
    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "success",
            "content": "not valid json",
        }

    generator = LLMCurriculumGenerator(
        llm_call=fake_call_llm,
    )

    with pytest.raises(
        RuntimeError,
        match="LLM curriculum response is invalid JSON",
    ):
        generator.generate(
            domain="Python",
            goal="能够独立编写简单程序",
        )


def test_llm_curriculum_generator_should_reject_missing_curriculum_topics():
    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "success",
            "content": """
            {
                "message": "课程已生成"
            }
            """,
        }

    generator = LLMCurriculumGenerator(
        llm_call=fake_call_llm,
    )

    with pytest.raises(
        RuntimeError,
        match="LLM curriculum response is missing curriculum_topics",
    ):
        generator.generate(
            domain="Python",
            goal="能够独立编写简单程序",
        )
