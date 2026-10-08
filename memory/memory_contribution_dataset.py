_REQUIRED_FIELDS = {
    "case_id",
    "query",
    "memory_context",
    "expected_effect",
    "evaluation_criteria",
}

_VALID_EXPECTED_EFFECTS = {
    "positive",
    "neutral",
    "negative",
}


def validate_memory_contribution_case(
    case,
):
    missing_fields = _REQUIRED_FIELDS - set(case)

    if missing_fields:
        raise ValueError(f"missing required fields: {sorted(missing_fields)}")

    expected_effect = case["expected_effect"]

    if expected_effect not in (_VALID_EXPECTED_EFFECTS):
        raise ValueError(f"invalid expected_effect: {expected_effect}")

    memory_context = case["memory_context"]

    if not isinstance(
        memory_context,
        list,
    ):
        raise ValueError("memory_context must be a list")

    evaluation_criteria = case["evaluation_criteria"]

    if (
        not isinstance(
            evaluation_criteria,
            list,
        )
        or not evaluation_criteria
    ):
        raise ValueError("evaluation_criteria must be a non-empty list")

    return True


def get_memory_contribution_evaluation_cases():
    cases = [
        {
            "case_id": ("relevant-learning-memory-should-help"),
            "query": ("Continue learning Tool Calling"),
            "memory_context": [
                {
                    "memory_key": ("learning:tool-calling"),
                    "content": (
                        "The learner previously "
                        "understood Tool Calling "
                        "at a basic level and the "
                        "next step is practical "
                        "tool execution."
                    ),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                (
                    "The answer should continue "
                    "from the learner's existing "
                    "basic understanding of "
                    "Tool Calling."
                ),
                (
                    "The answer should move "
                    "toward practical tool "
                    "execution rather than "
                    "restarting from zero."
                ),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "practical",
                    "tool",
                ],
                "forbidden_phrases": [
                    "start from zero",
                ],
            },
            "benchmark_answers": {
                "without_memory": (
                    "Tool Calling allows models to invoke external functions."
                ),
                "with_memory": ("Let's build a practical Tool Calling workflow."),
            },
        },
        {
            "case_id": ("irrelevant-profile-memory-should-be-neutral"),
            "query": ("Explain how Python lists work"),
            "memory_context": [
                {
                    "memory_key": ("profile:preferred-time"),
                    "content": ("The learner prefers studying in the afternoon."),
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                ("The answer should accurately explain Python lists."),
                (
                    "The unrelated study-time "
                    "preference should not "
                    "materially change the "
                    "technical explanation."
                ),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "python",
                    "list",
                ],
                "forbidden_phrases": [
                    "afternoon",
                ],
            },
            "benchmark_answers": {
                "without_memory": ("A Python list stores ordered items."),
                "with_memory": ("A Python list stores ordered items."),
            },
        },
        {
            "case_id": ("contradictory-learning-memory-should-hurt"),
            "query": ("Continue learning Tool Calling"),
            "memory_context": [
                {
                    "memory_key": ("learning:stale-tool-calling"),
                    "content": (
                        "The learner has already "
                        "fully mastered Tool Calling "
                        "and should skip all further "
                        "practice."
                    ),
                },
            ],
            "expected_effect": "negative",
            "evaluation_criteria": [
                (
                    "The answer should not "
                    "incorrectly assume complete "
                    "mastery of Tool Calling."
                ),
                (
                    "The answer should preserve "
                    "useful practice when further "
                    "practice is still appropriate."
                ),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "practice",
                ],
                "forbidden_phrases": [
                    "fully mastered",
                    "skip all further practice",
                ],
            },
            "benchmark_answers": {
                "without_memory": (
                    "Continue with practice to strengthen your Tool Calling skills."
                ),
                "with_memory": (
                    "You have fully mastered Tool Calling "
                    "and should skip all further practice."
                ),
            },
        },
    ]

    for case in cases:
        validate_memory_contribution_case(case)

    return cases
