from memory.memory_defense_runner import (
    run_memory_defense_evaluation,
)


def test_memory_defense_runner_should_evaluate_cases():
    cases = [
        {
            "case_id": "blocked-case",
            "query": "Continue Python",
            "memory_context": {
                "profile": [],
                "skill": [],
                "learning": [
                    {
                        "memory_key": ("learning:false"),
                        "content": "False.",
                        "confidence": 0.0,
                    },
                ],
                "project": [],
                "experience": [],
            },
            "target_memory_key": ("learning:false"),
            "expected_defense": ("blocked"),
        },
    ]

    report = run_memory_defense_evaluation(cases)

    assert report["summary"] == {
        "total_cases": 1,
        "correct_cases": 1,
        "error_cases": 0,
        "accuracy": 1.0,
    }

    assert report["errors"] == []


def test_memory_defense_runner_should_handle_empty_cases():
    report = run_memory_defense_evaluation([])

    assert report == {
        "results": [],
        "errors": [],
        "summary": {
            "total_cases": 0,
            "correct_cases": 0,
            "error_cases": 0,
            "accuracy": 0.0,
        },
    }
