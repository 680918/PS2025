from learning.next_task import build_next_learning_task
from planning.learning_planner import LearningPlanDecision


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


def test_build_next_learning_task_should_pass_evaluation_to_prompt():
    journey = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
    }

    continuity = {
        "has_previous_session": True,
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 80,
        "difficulty": "听力速度较快",
        "next_step": "练习慢速英语听力",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 60,
        "latest_understanding": 80,
        "understanding_change": 20,
        "trend": "improving",
    }

    result = build_next_learning_task(
        journey=journey,
        continuity=continuity,
        evaluation=evaluation,
    )

    assert result["context"]["evaluation"] == evaluation

    assert "已完成学习：3" in result["prompt"]
    assert "理解程度变化：20" in result["prompt"]
    assert "improving" in result["prompt"]

    assert "听力速度较快" in result["prompt"]
    assert "练习慢速英语听力" in result["prompt"]


def test_build_next_learning_task_should_pass_planning_decision_to_prompt():
    journey = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
    }

    continuity = {
        "has_previous_session": True,
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 60,
        "difficulty": "语速太快，跟不上",
        "next_step": "先练习慢速英语听力",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 80,
        "latest_understanding": 60,
        "understanding_change": -20,
        "trend": "declining",
    }

    planning_decision = {
        "topic": "英语听力",
        "action": "continue",
        "reason": "围绕语速问题调整练习，适当减小单次任务量。",
        "next_topic": None,
    }

    result = build_next_learning_task(
        journey=journey,
        continuity=continuity,
        evaluation=evaluation,
        planning_decision=planning_decision,
    )

    assert result["context"]["evaluation"] == evaluation
    assert result["context"]["planning_decision"] == planning_decision

    assert "教学调整建议" in result["prompt"]
    assert "围绕语速问题调整练习" in result["prompt"]
    assert "语速太快，跟不上" in result["prompt"]
    assert "先练习慢速英语听力" in result["prompt"]


def test_build_next_learning_task_should_accept_planning_decision_object():
    journey = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
    }

    continuity = {
        "has_previous_session": True,
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 60,
        "difficulty": "语速太快，跟不上",
        "next_step": "先练习慢速英语听力",
    }

    planning_decision = LearningPlanDecision(
        topic="英语听力",
        action="continue",
        reason="围绕语速问题调整练习，减小单次任务量。",
        next_topic=None,
    )

    result = build_next_learning_task(
        journey=journey,
        continuity=continuity,
        planning_decision=planning_decision,
    )

    assert result["context"]["planning_decision"] == {
        "topic": "英语听力",
        "action": "continue",
        "reason": "围绕语速问题调整练习，减小单次任务量。",
        "next_topic": None,
    }

    assert "教学调整建议" in result["prompt"]
    assert "围绕语速问题调整练习" in result["prompt"]


def test_next_learning_task_should_continue_current_unfinished_session():
    journey = {
        "domain": "AI Agent",
        "goal": "理解并实践 Tool Calling 与 Memory 的基本协作",
    }

    continuity = {
        "has_current_session": True,
        "current_session_id": "session_current",
        "current_topic": "Tool Calling",
        "current_understanding_score": None,
        "current_difficulty": None,
        "current_next_step": None,
        "has_previous_session": False,
    }

    result = build_next_learning_task(
        journey=journey,
        continuity=continuity,
    )

    context = result["context"]
    prompt = result["prompt"]

    assert context["has_current_session"] is True
    assert context["current_topic"] == "Tool Calling"

    assert "Tool Calling" in prompt
    assert "这是第一次学习" not in prompt
