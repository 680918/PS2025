_REQUIRED_FIELDS = {
    "case_id",
    "description",
    "existing_memory",
    "incoming_memory",
    "expected_conflict",
    "expected_reason",
}


def validate_memory_conflict_case(
    case,
):
    missing_fields = _REQUIRED_FIELDS - set(case)

    if missing_fields:
        raise ValueError(f"missing required fields: {sorted(missing_fields)}")

    if not isinstance(
        case["expected_conflict"],
        bool,
    ):
        raise ValueError("expected_conflict must be a bool")

    for field_name in (
        "existing_memory",
        "incoming_memory",
    ):
        memory = case[field_name]

        if not isinstance(memory, dict):
            raise ValueError(f"{field_name} must be a dict")

        for required_memory_field in (
            "memory_type",
            "memory_key",
            "content",
        ):
            if required_memory_field not in memory:
                raise ValueError(f"{field_name} missing {required_memory_field}")

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


def get_memory_conflict_cases():
    cases = [
        {
            "case_id": ("same-slot-content-changed"),
            "description": (
                "Changed content in the same Memory slot should be detected."
            ),
            "existing_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("The learner still needs Python fundamentals."),
            },
            "incoming_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("The learner has fully mastered Python."),
            },
            "expected_conflict": True,
            "expected_reason": ("same_slot_content_changed"),
        },
        {
            "case_id": ("same-slot-same-content"),
            "description": (
                "Identical content in the same slot should not be a conflict."
            ),
            "existing_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("Needs Python practice."),
            },
            "incoming_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("Needs Python practice."),
            },
            "expected_conflict": False,
            "expected_reason": ("same_content"),
        },
        {
            "case_id": ("same-slot-whitespace-change"),
            "description": (
                "Whitespace-only differences should normalize to the same content."
            ),
            "existing_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("Needs Python practice."),
            },
            "incoming_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("  Needs   Python practice.  "),
            },
            "expected_conflict": False,
            "expected_reason": ("same_content"),
        },
        {
            "case_id": ("different-memory-key"),
            "description": ("Different memory keys represent different slots."),
            "existing_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("Needs Python practice."),
            },
            "incoming_memory": {
                "memory_type": "learning",
                "memory_key": ("tool-calling-level"),
                "content": ("Tool Calling basics understood."),
            },
            "expected_conflict": False,
            "expected_reason": ("different_slot"),
        },
        {
            "case_id": ("different-memory-type"),
            "description": (
                "The same key under a different memory type is a different slot."
            ),
            "existing_memory": {
                "memory_type": "learning",
                "memory_key": "python-level",
                "content": ("Needs Python practice."),
            },
            "incoming_memory": {
                "memory_type": "skill",
                "memory_key": "python-level",
                "content": ("Python skill level is low."),
            },
            "expected_conflict": False,
            "expected_reason": ("different_slot"),
        },
    ]

    for case in cases:
        validate_memory_conflict_case(case)

    return cases
