from agent.context_evaluation import (
    evaluate_policy_compliance,
    evaluate_trace_completeness,
    evaluate_conflict_detection,
)


def test_policy_compliance_should_pass_when_winner_matches_priority():

    trace = {
        "learning.current_topic": {
            "winner": "conversation",
            "priority": [
                "conversation",
                "learning_continuity",
                "memory",
            ],
        }
    }

    result = evaluate_policy_compliance(
        trace,
    )

    assert result["learning.current_topic"].passed is True


def test_policy_compliance_should_fail_when_winner_breaks_priority():

    trace = {
        "learning.current_topic": {
            "winner": "memory",
            "priority": [
                "conversation",
                "learning_continuity",
                "memory",
            ],
        }
    }

    result = evaluate_policy_compliance(
        trace,
    )

    assert result["learning.current_topic"].passed is False


def test_trace_completeness_should_pass_when_required_fields_exist():

    trace = {
        "learning.current_topic": {
            "winner": "conversation",
            "value": "Memory",
            "policy_name": "LEARNING_POLICY",
            "priority": [
                "conversation",
                "learning_continuity",
                "memory",
            ],
        }
    }

    result = evaluate_trace_completeness(
        trace,
    )

    assert result["learning.current_topic"].passed is True


def test_trace_completeness_should_fail_when_fields_missing():

    trace = {
        "learning.current_topic": {
            "winner": "conversation",
        }
    }

    result = evaluate_trace_completeness(
        trace,
    )

    assert result["learning.current_topic"].passed is False


def test_conflict_detection_should_pass_when_conflict_detected():

    expected = {
        "learning.current_topic": [
            "Memory",
            "Tool Calling",
        ]
    }

    actual = {
        "learning.current_topic": [
            "Memory",
            "Tool Calling",
        ]
    }

    result = evaluate_conflict_detection(
        expected,
        actual,
    )

    assert result["learning.current_topic"].passed is True


def test_conflict_detection_should_fail_when_conflict_missing():

    expected = {
        "learning.current_topic": [
            "Memory",
            "Tool Calling",
        ]
    }

    actual = {}

    result = evaluate_conflict_detection(
        expected,
        actual,
    )

    assert result["learning.current_topic"].passed is False
