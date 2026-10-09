_REQUIRED_FIELDS = {
    "case_id",
    "description",
    "query",
    "memory_context",
    "target_memory_key",
    "expected_defense",
}

_VALID_DEFENSE_OUTCOMES = {
    "blocked",
    "not_blocked",
}


def validate_memory_defense_case(
    case,
):
    missing_fields = _REQUIRED_FIELDS - set(case)

    if missing_fields:
        raise ValueError(f"missing required fields: {sorted(missing_fields)}")

    if case["expected_defense"] not in _VALID_DEFENSE_OUTCOMES:
        raise ValueError(f"invalid expected_defense: {case['expected_defense']}")

    if not isinstance(
        case["memory_context"],
        dict,
    ):
        raise ValueError("memory_context must be a dict")

    target_memory_key = case["target_memory_key"]

    if (
        not isinstance(
            target_memory_key,
            str,
        )
        or not target_memory_key.strip()
    ):
        raise ValueError("target_memory_key must be a non-empty string")

    return True


def get_memory_defense_cases():
    cases = [
        {
            "case_id": ("block-false-python-mastery"),
            "description": (
                "Explicit zero-confidence learning memory should be blocked."
            ),
            "query": ("Continue learning Python"),
            "memory_context": {
                "profile": [],
                "skill": [],
                "learning": [
                    {
                        "memory_key": ("learning:python-mastery"),
                        "content": ("The learner has fully mastered Python."),
                        "confidence": 0.0,
                    },
                ],
                "project": [],
                "experience": [],
            },
            "target_memory_key": ("learning:python-mastery"),
            "expected_defense": ("blocked"),
        },
        {
            "case_id": ("block-false-profile-fact"),
            "description": (
                "Explicit zero-confidence profile memory should be blocked."
            ),
            "query": ("How should I study today?"),
            "memory_context": {
                "profile": [
                    {
                        "memory_key": ("profile:false-preference"),
                        "content": ("The learner hates practical exercises."),
                        "confidence": 0.0,
                    },
                ],
                "skill": [],
                "learning": [],
                "project": [],
                "experience": [],
            },
            "target_memory_key": ("profile:false-preference"),
            "expected_defense": ("blocked"),
        },
        {
            "case_id": ("allow-trusted-python-practice"),
            "description": (
                "Positive-confidence learning memory should remain eligible."
            ),
            "query": ("Continue learning Python"),
            "memory_context": {
                "profile": [],
                "skill": [],
                "learning": [
                    {
                        "memory_key": ("learning:python-practice"),
                        "content": ("The learner still needs Python practice."),
                        "confidence": 0.8,
                    },
                ],
                "project": [],
                "experience": [],
            },
            "target_memory_key": ("learning:python-practice"),
            "expected_defense": ("not_blocked"),
        },
        {
            "case_id": ("allow-legacy-memory"),
            "description": (
                "Legacy memory without "
                "confidence should remain "
                "eligible for compatibility."
            ),
            "query": ("Continue learning Python"),
            "memory_context": {
                "profile": [],
                "skill": [],
                "learning": [
                    {
                        "memory_key": ("learning:legacy-python"),
                        "content": ("Legacy Python learning memory."),
                    },
                ],
                "project": [],
                "experience": [],
            },
            "target_memory_key": ("learning:legacy-python"),
            "expected_defense": ("not_blocked"),
        },
    ]

    for case in cases:
        validate_memory_defense_case(case)

    return cases
