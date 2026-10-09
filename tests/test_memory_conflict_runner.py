from memory.memory_conflict_runner import (
    run_memory_conflict_evaluation,
)


def test_conflict_runner_should_summarize_results():
    cases = [
        {
            "case_id": "conflict-case",
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
        },
    ]

    report = run_memory_conflict_evaluation(cases)

    assert report["summary"] == {
        "total_cases": 1,
        "correct_cases": 1,
        "error_cases": 0,
        "accuracy": 1.0,
    }

    assert report["errors"] == []


def test_conflict_runner_should_handle_empty_cases():
    report = run_memory_conflict_evaluation([])

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
