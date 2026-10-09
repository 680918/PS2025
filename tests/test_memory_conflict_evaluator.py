from memory.memory_conflict_evaluator import (
    evaluate_memory_conflict_case,
)


def test_conflict_evaluator_should_report_correct_detection():
    case = {
        "case_id": "changed-content",
        "existing_memory": {
            "memory_type": "learning",
            "memory_key": "python-level",
            "content": "Needs practice.",
        },
        "incoming_memory": {
            "memory_type": "learning",
            "memory_key": "python-level",
            "content": "Fully mastered.",
        },
        "expected_conflict": True,
        "expected_reason": ("same_slot_content_changed"),
    }

    result = evaluate_memory_conflict_case(case)

    assert result == {
        "case_id": "changed-content",
        "expected_conflict": True,
        "actual_conflict": True,
        "expected_reason": ("same_slot_content_changed"),
        "actual_reason": ("same_slot_content_changed"),
        "is_correct": True,
    }


def test_conflict_evaluator_should_report_wrong_reason_as_failure():
    case = {
        "case_id": "reason-check",
        "existing_memory": {
            "memory_type": "learning",
            "memory_key": "python-level",
            "content": "Same.",
        },
        "incoming_memory": {
            "memory_type": "learning",
            "memory_key": "python-level",
            "content": "Same.",
        },
        "expected_conflict": False,
        "expected_reason": ("different_slot"),
    }

    result = evaluate_memory_conflict_case(case)

    assert result["actual_conflict"] is False

    assert result["actual_reason"] == "same_content"

    assert result["is_correct"] is False
