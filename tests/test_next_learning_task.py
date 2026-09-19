from learning.next_task import (
    build_next_learning_task,
)


def test_build_next_learning_task_should_return_context_and_prompt():
    journey = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
    }

    continuity = {
        "has_previous_session": True,
        "topic": "英语听力",
        "understanding_score": 80,
        "difficulty": "听力速度较快",
        "next_step": "练习慢速英语听力",
    }

    result = build_next_learning_task(
        journey=journey,
        continuity=continuity,
    )

    assert result["context"]["domain"] == "英语"
    assert result["context"]["recommended_next_step"] == "练习慢速英语听力"

    assert "英语" in result["prompt"]
    assert "听力速度较快" in result["prompt"]
    assert "练习慢速英语听力" in result["prompt"]
