from learning.next_task import (
    build_next_learning_task_context,
)


def test_build_next_learning_task_context_should_combine_journey_and_continuity():
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

    context = build_next_learning_task_context(
        journey=journey,
        continuity=continuity,
    )

    assert context["domain"] == "英语"
    assert context["goal"] == "6个月达到日常交流"
    assert context["previous_topic"] == "英语听力"
    assert context["understanding_score"] == 80
    assert context["difficulty"] == "听力速度较快"
    assert context["recommended_next_step"] == "练习慢速英语听力"
    assert context["has_previous_session"] is True


def test_build_next_learning_task_context_should_handle_first_session():
    journey = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
    }

    continuity = {
        "has_previous_session": False,
    }

    context = build_next_learning_task_context(
        journey=journey,
        continuity=continuity,
    )

    assert context["domain"] == "英语"
    assert context["goal"] == "6个月达到日常交流"

    assert context["previous_topic"] is None
    assert context["understanding_score"] is None
    assert context["difficulty"] is None
    assert context["recommended_next_step"] is None
    assert context["has_previous_session"] is False


def test_uncompleted_session_should_be_treated_as_first_learning():
    journey = {
        "domain": "英语",
        "goal": "6个月达到日常交流",
    }

    continuity = {
        "has_previous_session": True,
        "topic": "英语",
        "completed": False,
        "understanding_score": None,
        "difficulty": None,
        "next_step": None,
    }

    context = build_next_learning_task_context(
        journey=journey,
        continuity=continuity,
    )

    assert context["has_previous_session"] is False
    assert context["previous_topic"] is None
    assert context["understanding_score"] is None
    assert context["difficulty"] is None
    assert context["recommended_next_step"] is None


def test_next_learning_task_context_should_include_journey_evaluation():
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

    context = build_next_learning_task_context(
        journey=journey,
        continuity=continuity,
        evaluation=evaluation,
    )

    assert context["domain"] == "英语"
    assert context["recommended_next_step"] == "练习慢速英语听力"

    assert context["evaluation"]["completed_sessions"] == 3
    assert context["evaluation"]["understanding_change"] == 20
    assert context["evaluation"]["trend"] == "improving"
