MEMORY_CONTRIBUTION_REGRESSION_BASELINE = {
    "total_cases": 3,
    "accuracy": 1.0,
    "cases": {
        ("relevant-learning-memory-should-help"): {
            "actual_effect": "positive",
            "contribution_delta": 0.25,
        },
        ("irrelevant-profile-memory-should-be-neutral"): {
            "actual_effect": "neutral",
            "contribution_delta": 0.0,
        },
        ("contradictory-learning-memory-should-hurt"): {
            "actual_effect": "negative",
            "contribution_delta": -0.75,
        },
    },
}
