from planning.journey_planning_adapter import (
    build_journey_planning_decision,
)
from planning.learning_planner import LearningPlanDecision
from learning.curriculum import CurriculumItem, LearningCurriculum


def test_insufficient_journey_data_should_continue_current_topic():
    continuity = {
        "has_previous_session": True,
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 70,
        "difficulty": "语速较快",
        "next_step": "继续练习慢速英语听力",
    }

    evaluation = {
        "completed_sessions": 1,
        "first_understanding": 70,
        "latest_understanding": 70,
        "understanding_change": None,
        "trend": "insufficient_data",
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
    )

    assert isinstance(decision, LearningPlanDecision)
    assert decision.topic == "英语听力"
    assert decision.action == "continue"
    assert decision.next_topic is None
    assert decision.reason


def test_improving_journey_should_not_automatically_advance():
    continuity = {
        "has_previous_session": True,
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 70,
        "difficulty": "语速较快",
        "next_step": "继续练习慢速英语听力",
    }

    evaluation = {
        "completed_sessions": 2,
        "first_understanding": 60,
        "latest_understanding": 70,
        "understanding_change": 10,
        "trend": "improving",
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
    )

    assert decision.action == "continue"
    assert decision.topic == "英语听力"
    assert decision.next_topic is None
    assert "自评" in decision.reason


def test_declining_journey_should_address_specific_difficulty():
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

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
    )

    assert decision.action == "continue"
    assert decision.topic == "英语听力"
    assert decision.next_topic is None

    assert "自评" in decision.reason
    assert "语速太快，跟不上" in decision.reason
    assert "先练习慢速英语听力" in decision.reason


def test_stable_journey_should_not_assume_learning_stagnation():
    continuity = {
        "has_previous_session": True,
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 82,
        "difficulty": "长句容易漏听",
        "next_step": "练习长句分段听力",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 80,
        "latest_understanding": 82,
        "understanding_change": 2,
        "trend": "stable",
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
    )

    assert decision.action == "continue"
    assert decision.topic == "英语听力"
    assert decision.next_topic is None

    assert "自评" in decision.reason
    assert "长句容易漏听" in decision.reason
    assert "练习长句分段听力" in decision.reason


def test_improving_journey_with_strong_previous_evidence_should_advance():
    continuity = {
        "has_previous_session": True,
        "session_id": "session_001",
        "completed": True,
        "topic": "Python函数",
        "understanding_score": 85,
        "difficulty": "长句偶尔漏听",
        "next_step": "进入下一节听力训练",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 70,
        "latest_understanding": 85,
        "understanding_change": 15,
        "trend": "improving",
    }

    previous_session_evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        previous_session_evidence_summary=previous_session_evidence_summary,
    )

    assert decision.action == "advance"
    assert decision.topic == "Python函数"
    assert decision.next_topic == "Python异常处理"


def test_advance_without_known_next_topic_should_not_claim_planned_next_lesson():
    continuity = {
        "has_previous_session": True,
        "session_id": "session_001",
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 85,
        "difficulty": "长句偶尔漏听",
        "next_step": "进入下一节听力训练",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 70,
        "latest_understanding": 85,
        "understanding_change": 15,
        "trend": "improving",
    }

    previous_session_evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        previous_session_evidence_summary=previous_session_evidence_summary,
    )

    assert decision.action == "advance"
    assert decision.topic == "英语听力"
    assert decision.next_topic is None
    assert "按原学习计划进入下一节" not in decision.reason


def test_weak_previous_evidence_should_trigger_review():
    continuity = {
        "has_previous_session": True,
        "session_id": "session_001",
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 85,
        "difficulty": "长句偶尔漏听",
        "next_step": "进行拓展听力练习",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 75,
        "latest_understanding": 85,
        "understanding_change": 10,
        "trend": "improving",
    }

    previous_session_evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 0,
            "weak": 2,
            "insufficient": 0,
        },
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        previous_session_evidence_summary=previous_session_evidence_summary,
    )

    assert decision.action == "review"
    assert "拓展" in decision.reason
    assert "验证" in decision.reason


def test_insufficient_previous_evidence_should_trigger_remediation():
    continuity = {
        "has_previous_session": True,
        "session_id": "session_001",
        "completed": True,
        "topic": "英语听力",
        "understanding_score": 78,
        "difficulty": "长句容易漏听",
        "next_step": "继续练习长句分段听力",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 70,
        "latest_understanding": 78,
        "understanding_change": 8,
        "trend": "improving",
    }

    previous_session_evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 1,
        "learning_signal": "insufficient_data",
        "quality_summary": {
            "strong": 1,
            "weak": 0,
            "insufficient": 1,
        },
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        previous_session_evidence_summary=previous_session_evidence_summary,
    )

    assert decision.action == "remediate"
    assert "补强" in decision.reason
    assert "测试" in decision.reason


def test_advance_should_prefer_journey_curriculum_over_global_path():
    continuity = {
        "has_previous_session": True,
        "session_id": "session_001",
        "completed": True,
        "topic": "Python函数",
        "understanding_score": 85,
        "difficulty": "长句偶尔漏听",
        "next_step": "进入下一节听力训练",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 70,
        "latest_understanding": 85,
        "understanding_change": 15,
        "trend": "improving",
    }

    previous_session_evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python函数"),
            CurriculumItem(position=2, topic="Python装饰器"),
        ],
    )

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        previous_session_evidence_summary=previous_session_evidence_summary,
        curriculum=curriculum,
    )

    assert decision.action == "advance"
    assert decision.topic == "Python函数"
    assert decision.next_topic == "Python装饰器"


def test_advance_should_not_fallback_when_curriculum_has_no_next_topic():
    continuity = {
        "has_previous_session": True,
        "session_id": "session_001",
        "completed": True,
        "topic": "Python函数",
        "understanding_score": 85,
        "difficulty": "长句偶尔漏听",
        "next_step": "进入下一节听力训练",
    }

    evaluation = {
        "completed_sessions": 3,
        "first_understanding": 70,
        "latest_understanding": 85,
        "understanding_change": 15,
        "trend": "improving",
    }

    previous_session_evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python函数"),
        ],
    )

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        previous_session_evidence_summary=previous_session_evidence_summary,
        curriculum=curriculum,
    )

    assert decision.action == "advance"
    assert decision.topic == "Python函数"
    assert decision.next_topic is None
