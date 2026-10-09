from memory.memory_conflict_resolution_runner import (
    run_memory_conflict_resolution_evaluation,
)


def test_resolution_runner_should_summarize_results():
    report = run_memory_conflict_resolution_evaluation([])

    assert report["summary"] == {
        "total_cases": 0,
        "correct_cases": 0,
        "error_cases": 0,
        "accuracy": 0.0,
    }

    assert report["errors"] == []

    assert report["category_summary"] == {
        "baseline": {
            "total_cases": 0,
            "correct_cases": 0,
            "error_cases": 0,
            "accuracy": 0.0,
        },
        "challenge": {
            "total_cases": 0,
            "correct_cases": 0,
            "error_cases": 0,
            "accuracy": 0.0,
        },
    }
