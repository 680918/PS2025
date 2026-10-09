from memory.memory_conflict_detector import (
    detect_memory_conflict,
)


def evaluate_memory_conflict_case(
    case,
):
    detection = detect_memory_conflict(
        case["existing_memory"],
        case["incoming_memory"],
    )

    actual_conflict = detection["has_conflict"]

    actual_reason = detection["reason"]

    expected_conflict = case["expected_conflict"]

    expected_reason = case["expected_reason"]

    return {
        "case_id": case["case_id"],
        "expected_conflict": (expected_conflict),
        "actual_conflict": (actual_conflict),
        "expected_reason": (expected_reason),
        "actual_reason": (actual_reason),
        "is_correct": (
            actual_conflict == expected_conflict and actual_reason == expected_reason
        ),
    }
