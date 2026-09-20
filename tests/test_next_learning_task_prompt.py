from learning.next_task import (
    build_next_learning_task_prompt,
)


def test_build_next_learning_task_prompt_should_include_learning_context():
    context = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
        "has_previous_session": True,
        "previous_topic": "英语听力",
        "understanding_score": 80,
        "difficulty": "听力速度较快",
        "recommended_next_step": "练习慢速英语听力",
    }

    prompt = build_next_learning_task_prompt(context)

    assert "英语" in prompt
    assert "6个月达到日常交流" in prompt
    assert "英语听力" in prompt
    assert "80" in prompt
    assert "听力速度较快" in prompt
    assert "练习慢速英语听力" in prompt


def test_build_next_learning_task_prompt_should_handle_first_session_without_fake_history():
    context = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
        "has_previous_session": False,
        "previous_topic": None,
        "understanding_score": None,
        "difficulty": None,
        "recommended_next_step": None,
    }

    prompt = build_next_learning_task_prompt(context)

    assert "这是第一次学习" in prompt
    assert "不要虚构之前的学习记录" in prompt

    assert "上一节主题：\nNone" not in prompt
    assert "当前难点：\nNone" not in prompt
    assert "建议下一步：\nNone" not in prompt


def test_next_learning_task_prompt_should_include_journey_evaluation():
    context = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
        "has_previous_session": True,
        "previous_topic": "英语听力",
        "understanding_score": 80,
        "difficulty": "听力速度较快",
        "recommended_next_step": "练习慢速英语听力",
        "evaluation": {
            "completed_sessions": 3,
            "first_understanding": 60,
            "latest_understanding": 80,
            "understanding_change": 20,
            "trend": "improving",
        },
    }

    prompt = build_next_learning_task_prompt(
        context=context,
    )

    assert "已完成学习：3" in prompt
    assert "首次理解程度：60" in prompt
    assert "最新理解程度：80" in prompt
    assert "理解程度变化：20" in prompt
    assert "improving" in prompt

    assert "听力速度较快" in prompt
    assert "练习慢速英语听力" in prompt

    assert "自评" in prompt
