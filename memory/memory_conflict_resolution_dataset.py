from memory.memory_conflict_detector import (
    detect_memory_conflict,
)


_REQUIRED_FIELDS = {
    "case_id",
    "category",
    "description",
    "existing_memory",
    "incoming_memory",
    "expected_resolution",
    "expected_reason",
}

_VALID_CATEGORIES = {
    "baseline",
    "challenge",
}

_VALID_RESOLUTIONS = {
    "keep_existing",
    "use_incoming",
}

_MEMORY_FIELDS = {
    "memory_type",
    "memory_key",
    "content",
    "importance",
    "confidence",
    "source",
    "updated_at",
}


def validate_memory_conflict_resolution_case(
    case,
):
    missing_fields = _REQUIRED_FIELDS - set(case)

    if missing_fields:
        raise ValueError(f"missing required fields: {sorted(missing_fields)}")

    if case["category"] not in _VALID_CATEGORIES:
        raise ValueError(f"invalid category: {case['category']}")

    if case["expected_resolution"] not in _VALID_RESOLUTIONS:
        raise ValueError(f"invalid expected_resolution: {case['expected_resolution']}")

    for field_name in (
        "existing_memory",
        "incoming_memory",
    ):
        memory = case[field_name]

        if not isinstance(memory, dict):
            raise ValueError(f"{field_name} must be a dict")

        missing_memory_fields = _MEMORY_FIELDS - set(memory)

        if missing_memory_fields:
            raise ValueError(
                f"{field_name} missing fields: {sorted(missing_memory_fields)}"
            )

    conflict = detect_memory_conflict(
        case["existing_memory"],
        case["incoming_memory"],
    )

    if not conflict["has_conflict"]:
        raise ValueError("resolution case must contain a memory conflict")

    expected_reason = case["expected_reason"]

    if (
        not isinstance(
            expected_reason,
            str,
        )
        or not expected_reason.strip()
    ):
        raise ValueError("expected_reason must be a non-empty string")

    return True


def _memory(
    *,
    content,
    importance,
    confidence,
    source,
    updated_at,
):
    return {
        "memory_type": "skill",
        "memory_key": "python_skill",
        "content": content,
        "importance": importance,
        "confidence": confidence,
        "source": source,
        "updated_at": updated_at,
    }


def get_memory_conflict_resolution_cases():
    cases = [
        {
            "case_id": ("keep-lower-confidence"),
            "category": "baseline",
            "description": (
                "Lower-confidence incoming "
                "memory should not replace "
                "the existing memory."
            ),
            "existing_memory": _memory(
                content="Needs Python practice.",
                importance=0.8,
                confidence=0.9,
                source="learning_feedback",
                updated_at=("2026-09-01T10:00:00"),
            ),
            "incoming_memory": _memory(
                content="Fully mastered Python.",
                importance=1.0,
                confidence=0.6,
                source="user_confirmed",
                updated_at=("2026-10-01T10:00:00"),
            ),
            "expected_resolution": ("keep_existing"),
            "expected_reason": ("new_confidence_lower"),
        },
        {
            "case_id": ("use-higher-confidence"),
            "category": "baseline",
            "description": (
                "Higher-confidence incoming memory should replace the existing memory."
            ),
            "existing_memory": _memory(
                content="Needs Python practice.",
                importance=0.8,
                confidence=0.6,
                source="learning_feedback",
                updated_at=("2026-09-01T10:00:00"),
            ),
            "incoming_memory": _memory(
                content="Python basics understood.",
                importance=0.8,
                confidence=0.9,
                source="learning_feedback",
                updated_at=("2026-10-01T10:00:00"),
            ),
            "expected_resolution": ("use_incoming"),
            "expected_reason": ("new_confidence_higher"),
        },
        {
            "case_id": ("keep-lower-importance"),
            "category": "baseline",
            "description": (
                "With equal confidence, lower "
                "importance should not replace "
                "the existing memory."
            ),
            "existing_memory": _memory(
                content="Needs Python practice.",
                importance=0.9,
                confidence=0.8,
                source="learning_feedback",
                updated_at=("2026-09-01T10:00:00"),
            ),
            "incoming_memory": _memory(
                content="Python basics understood.",
                importance=0.6,
                confidence=0.8,
                source="learning_feedback",
                updated_at=("2026-10-01T10:00:00"),
            ),
            "expected_resolution": ("keep_existing"),
            "expected_reason": ("new_importance_lower"),
        },
        {
            "case_id": ("use-more-reliable-source"),
            "category": "baseline",
            "description": (
                "With equal quality scores, "
                "a more reliable source should "
                "replace the existing memory."
            ),
            "existing_memory": _memory(
                content="Needs Python practice.",
                importance=0.8,
                confidence=0.9,
                source="agent_inference",
                updated_at=("2026-09-01T10:00:00"),
            ),
            "incoming_memory": _memory(
                content="Python basics understood.",
                importance=0.8,
                confidence=0.9,
                source="user_confirmed",
                updated_at=("2026-10-01T10:00:00"),
            ),
            "expected_resolution": ("use_incoming"),
            "expected_reason": ("new_source_more_reliable"),
        },
        {
            "case_id": ("use-newer-memory"),
            "category": "baseline",
            "description": (
                "With equal quality and source, newer information should win."
            ),
            "existing_memory": _memory(
                content="Needs Python practice.",
                importance=0.8,
                confidence=0.9,
                source="learning_feedback",
                updated_at=("2026-08-01T10:00:00"),
            ),
            "incoming_memory": _memory(
                content="Python basics understood.",
                importance=0.8,
                confidence=0.9,
                source="learning_feedback",
                updated_at=("2026-10-01T10:00:00"),
            ),
            "expected_resolution": ("use_incoming"),
            "expected_reason": ("newer_or_equal_timestamp"),
        },
        {
            "case_id": ("keep-older-memory"),
            "category": "baseline",
            "description": (
                "With equal quality and source, "
                "older incoming information "
                "should not replace newer data."
            ),
            "existing_memory": _memory(
                content="Python basics understood.",
                importance=0.8,
                confidence=0.9,
                source="learning_feedback",
                updated_at=("2026-10-01T10:00:00"),
            ),
            "incoming_memory": _memory(
                content="Needs Python practice.",
                importance=0.8,
                confidence=0.9,
                source="learning_feedback",
                updated_at=("2026-08-01T10:00:00"),
            ),
            "expected_resolution": ("keep_existing"),
            "expected_reason": ("older_timestamp"),
        },
        {
            "case_id": ("challenge-user-confirmed-vs-agent-confidence"),
            "category": "challenge",
            "description": (
                "A slightly higher-confidence "
                "agent inference should not "
                "override a user-confirmed fact."
            ),
            "existing_memory": _memory(
                content="Needs Python practice.",
                importance=0.8,
                confidence=0.90,
                source="user_confirmed",
                updated_at=("2026-09-01T10:00:00"),
            ),
            "incoming_memory": _memory(
                content="Fully mastered Python.",
                importance=0.8,
                confidence=0.95,
                source="agent_inference",
                updated_at=("2026-10-01T10:00:00"),
            ),
            "expected_resolution": ("keep_existing"),
            "expected_reason": ("new_source_less_reliable"),
        },
    ]

    for case in cases:
        validate_memory_conflict_resolution_case(case)

    return cases
