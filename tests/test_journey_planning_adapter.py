from planning.journey_planning_adapter import (
    build_journey_planning_decision,
)
from planning.learning_planner import LearningPlanDecision


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
