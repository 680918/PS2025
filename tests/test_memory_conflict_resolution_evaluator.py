from memory.memory_conflict_resolution_evaluator import (
    evaluate_memory_conflict_resolution_case,
)


def test_resolution_evaluator_should_report_matching_policy_decision():
    case = {
        "case_id": "lower-confidence",
        "category": "baseline",
        "existing_memory": {
            "memory_type": "skill",
            "memory_key": "python_skill",
            "content": "Needs practice.",
            "importance": 0.8,
            "confidence": 0.9,
            "source": "learning_feedback",
            "updated_at": ("2026-09-01T10:00:00"),
        },
        "incoming_memory": {
            "memory_type": "skill",
            "memory_key": "python_skill",
            "content": "Fully mastered.",
            "importance": 0.8,
            "confidence": 0.6,
            "source": "learning_feedback",
            "updated_at": ("2026-10-01T10:00:00"),
        },
        "expected_resolution": ("keep_existing"),
        "expected_reason": ("new_confidence_lower"),
    }

    result = evaluate_memory_conflict_resolution_case(case)

    assert result == {
        "case_id": "lower-confidence",
        "category": "baseline",
        "expected_resolution": ("keep_existing"),
        "actual_resolution": ("keep_existing"),
        "expected_reason": ("new_confidence_lower"),
        "actual_reason": ("new_confidence_lower"),
        "is_correct": True,
    }


def test_resolution_evaluator_should_match_repaired_source_guard():
    case = {
        "case_id": "source-challenge",
        "category": "challenge",
        "existing_memory": {
            "memory_type": "skill",
            "memory_key": "python_skill",
            "content": "User-confirmed fact.",
            "importance": 0.8,
            "confidence": 0.90,
            "source": "user_confirmed",
            "updated_at": ("2026-09-01T10:00:00"),
        },
        "incoming_memory": {
            "memory_type": "skill",
            "memory_key": "python_skill",
            "content": "Agent inference.",
            "importance": 0.8,
            "confidence": 0.95,
            "source": "agent_inference",
            "updated_at": ("2026-10-01T10:00:00"),
        },
        "expected_resolution": ("keep_existing"),
        "expected_reason": ("new_source_less_reliable"),
    }

    result = evaluate_memory_conflict_resolution_case(case)

    assert result["actual_resolution"] == "keep_existing"

    assert result["actual_reason"] == "new_source_less_reliable"

    assert result["is_correct"] is True


def test_resolution_evaluator_should_expose_injected_policy_gap():
    case = {
        "case_id": "source-challenge",
        "category": "challenge",
        "existing_memory": {
            "memory_type": "skill",
            "memory_key": "python_skill",
            "content": "User-confirmed fact.",
            "importance": 0.8,
            "confidence": 0.90,
            "source": "user_confirmed",
            "updated_at": ("2026-09-01T10:00:00"),
        },
        "incoming_memory": {
            "memory_type": "skill",
            "memory_key": "python_skill",
            "content": "Agent inference.",
            "importance": 0.8,
            "confidence": 0.95,
            "source": "agent_inference",
            "updated_at": ("2026-10-01T10:00:00"),
        },
        "expected_resolution": ("keep_existing"),
        "expected_reason": ("new_source_less_reliable"),
    }

    class FakeDecision:
        allowed = True
        reason = "new_confidence_higher"

    class FakePolicy:
        def evaluate(
            self,
            existing,
            new_confidence,
            new_importance,
            new_source,
            new_updated_at,
        ):
            return FakeDecision()

    result = evaluate_memory_conflict_resolution_case(
        case,
        policy=FakePolicy(),
    )

    assert result["actual_resolution"] == "use_incoming"

    assert result["actual_reason"] == "new_confidence_higher"

    assert result["is_correct"] is False
