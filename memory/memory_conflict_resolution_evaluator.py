from memory.models import MemoryRecord
from memory.policy import MemoryPolicy


def _create_existing_memory(
    data,
):
    return MemoryRecord(
        memory_type=data["memory_type"],
        memory_key=data["memory_key"],
        content=data["content"],
        importance=data["importance"],
        confidence=data["confidence"],
        source=data["source"],
        updated_at=data["updated_at"],
    )


def evaluate_memory_conflict_resolution_case(
    case,
    policy=None,
):
    policy = policy or MemoryPolicy()

    existing_data = case["existing_memory"]

    incoming = case["incoming_memory"]

    existing = _create_existing_memory(existing_data)

    decision = policy.evaluate(
        existing,
        new_confidence=(incoming["confidence"]),
        new_importance=(incoming["importance"]),
        new_source=(incoming["source"]),
        new_updated_at=(incoming["updated_at"]),
    )

    if decision.allowed:
        actual_resolution = "use_incoming"
    else:
        actual_resolution = "keep_existing"

    expected_resolution = case["expected_resolution"]

    expected_reason = case["expected_reason"]

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "expected_resolution": (expected_resolution),
        "actual_resolution": (actual_resolution),
        "expected_reason": (expected_reason),
        "actual_reason": (decision.reason),
        "is_correct": (
            actual_resolution == expected_resolution
            and decision.reason == expected_reason
        ),
    }
