from agent.context_policy import get_conflict_priority


def test_get_conflict_priority_should_return_learning_policy():

    priority = get_conflict_priority(
        "learning.current_topic",
    )

    assert priority == [
        "conversation",
        "learning_continuity",
        "memory",
    ]


def test_get_conflict_priority_should_return_user_preference_policy():

    priority = get_conflict_priority(
        "user.preference.explanation_style",
    )

    assert priority == [
        "conversation",
        "memory",
    ]


def test_get_conflict_priority_should_return_completed_learning_policy():

    priority = get_conflict_priority(
        "learning.completed_understanding",
    )

    assert priority == [
        "memory",
        "conversation",
    ]


def test_learning_current_field_should_prefer_conversation():

    priority = get_conflict_priority(
        "learning.current_topic",
    )

    assert priority == [
        "conversation",
        "learning_continuity",
        "memory",
    ]


def test_get_conflict_priority_should_keep_specific_rule_before_general_rule():

    priority = get_conflict_priority(
        "learning.completed_understanding",
    )

    assert priority == [
        "memory",
        "conversation",
    ]


def test_get_conflict_policy_name_should_return_learning_policy():

    from agent.context_policy import (
        get_conflict_policy_name,
    )

    assert (
        get_conflict_policy_name(
            "learning.current_topic",
        )
        == "LEARNING_POLICY"
    )
