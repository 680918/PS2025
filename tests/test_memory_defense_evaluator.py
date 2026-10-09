from memory.memory_defense_evaluator import (
    evaluate_memory_defense_case,
)


def test_memory_defense_should_report_untrusted_memory_as_blocked():
    case = {
        "case_id": ("block-false-python-mastery"),
        "query": "Continue learning Python",
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
        "expected_defense": "blocked",
    }

    result = evaluate_memory_defense_case(case)

    assert result == {
        "case_id": ("block-false-python-mastery"),
        "target_memory_key": ("learning:python-mastery"),
        "expected_defense": "blocked",
        "actual_defense": "blocked",
        "is_correct": True,
        "blocked_memory_keys": [
            "learning:python-mastery",
        ],
    }


def test_memory_defense_should_not_block_trusted_memory():
    case = {
        "case_id": ("allow-python-practice"),
        "query": "Continue learning Python",
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
        "expected_defense": "not_blocked",
    }

    result = evaluate_memory_defense_case(case)

    assert result["actual_defense"] == "not_blocked"

    assert result["is_correct"] is True

    assert result["blocked_memory_keys"] == []
