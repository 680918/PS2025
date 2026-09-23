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


def test_next_learning_task_prompt_should_include_planning_decision():
    context = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
        "has_previous_session": True,
        "previous_topic": "英语听力",
        "understanding_score": 60,
        "difficulty": "语速太快，跟不上",
        "recommended_next_step": "先练习慢速英语听力",
        "evaluation": {
            "completed_sessions": 3,
            "first_understanding": 80,
            "latest_understanding": 60,
            "understanding_change": -20,
            "trend": "declining",
        },
        "planning_decision": {
            "topic": "英语听力",
            "action": "continue",
            "reason": "围绕语速问题调整练习，适当减小单次任务量。",
            "next_topic": None,
        },
    }

    prompt = build_next_learning_task_prompt(context)

    assert "教学调整建议" in prompt
    assert "continue" in prompt
    assert "围绕语速问题调整练习，适当减小单次任务量。" in prompt

    assert "语速太快，跟不上" in prompt
    assert "先练习慢速英语听力" in prompt
    assert "declining" in prompt


def test_advance_should_generate_progression_instruction():
    context = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
        "has_previous_session": True,
        "previous_topic": "英语听力",
        "understanding_score": 85,
        "difficulty": "长句偶尔漏听",
        "recommended_next_step": "进入下一节听力训练",
        "planning_decision": {
            "topic": "英语听力",
            "action": "advance",
            "reason": "上一节证据充分且学习趋势改善。",
            "next_topic": "英语进阶听力",
        },
    }

    prompt = build_next_learning_task_prompt(context)

    assert "教学动作：advance" in prompt
    assert "下一主题：英语进阶听力" in prompt
    assert "请围绕已确定的下一主题“英语进阶听力”" in prompt
    assert "优先围绕上一节的难点和建议下一步安排任务" not in prompt


def test_advance_without_next_topic_should_not_claim_a_known_learning_path():
    context = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
        "has_previous_session": True,
        "previous_topic": "英语听力",
        "understanding_score": 85,
        "difficulty": "长句偶尔漏听",
        "recommended_next_step": "进入下一节听力训练",
        "planning_decision": {
            "topic": "英语听力",
            "action": "advance",
            "reason": "上一节学习证据充分且学习趋势改善，支持进入下一阶段学习。",
            "next_topic": None,
        },
    }

    prompt = build_next_learning_task_prompt(context)

    assert "教学动作：advance" in prompt
    assert "尚未确定具体的下一主题" in prompt
    assert "请按原学习计划进入下一节" not in prompt
    assert "下一主题：None" not in prompt
