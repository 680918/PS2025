import pytest

from memory.memory_calibration_dataset import (
    get_memory_calibration_cases,
    validate_memory_calibration_case,
)


def test_memory_calibration_dataset_should_contain_12_cases():
    cases = get_memory_calibration_cases()

    assert len(cases) == 12


def test_memory_calibration_dataset_should_have_three_cases_per_category():
    cases = get_memory_calibration_cases()

    counts = {}

    for case in cases:
        category = case["category"]
        counts[category] = counts.get(category, 0) + 1

    assert counts == {
        "helpful": 3,
        "neutral": 3,
        "harmful": 3,
        "ambiguous": 3,
    }


def test_memory_calibration_dataset_should_have_unique_case_ids():
    cases = get_memory_calibration_cases()

    case_ids = [case["case_id"] for case in cases]

    assert len(case_ids) == len(set(case_ids))


def test_memory_calibration_dataset_should_validate_all_cases():
    cases = get_memory_calibration_cases()

    for case in cases:
        assert validate_memory_calibration_case(case)


def test_ambiguous_category_should_still_use_standard_effects():
    cases = get_memory_calibration_cases()

    ambiguous_cases = [case for case in cases if case["category"] == "ambiguous"]

    for case in ambiguous_cases:
        assert case["expected_effect"] in {
            "positive",
            "neutral",
            "negative",
        }


def test_memory_calibration_case_should_reject_invalid_category():
    case = {
        "case_id": "invalid-category",
        "category": "unknown",
        "domain": "python",
        "description": "Invalid category.",
        "query": "Explain Python.",
        "memory_context": [],
        "expected_effect": "neutral",
        "evaluation_criteria": [
            "Explain Python accurately.",
        ],
        "rule_scoring": {
            "required_phrases": [],
            "forbidden_phrases": [],
        },
        "benchmark_answers": {
            "without_memory": "Answer A.",
            "with_memory": "Answer B.",
        },
    }

    with pytest.raises(
        ValueError,
        match="invalid category",
    ):
        validate_memory_calibration_case(case)


def test_memory_calibration_case_should_reject_invalid_effect():
    case = {
        "case_id": "invalid-effect",
        "category": "ambiguous",
        "domain": "python",
        "description": "Invalid effect.",
        "query": "Explain Python.",
        "memory_context": [],
        "expected_effect": "ambiguous",
        "evaluation_criteria": [
            "Explain Python accurately.",
        ],
        "rule_scoring": {
            "required_phrases": [],
            "forbidden_phrases": [],
        },
        "benchmark_answers": {
            "without_memory": "Answer A.",
            "with_memory": "Answer B.",
        },
    }

    with pytest.raises(
        ValueError,
        match="invalid expected_effect",
    ):
        validate_memory_calibration_case(case)


def test_harmful_python_mastery_should_include_reference_context():
    cases = get_memory_calibration_cases()

    case = next(
        case for case in cases if case["case_id"] == "harmful-false-python-mastery"
    )

    assert case["reference_context"] == [
        (
            "The learner has not fully mastered "
            "Python and still needs foundational "
            "practice."
        ),
    ]


def test_memory_calibration_case_should_reject_invalid_reference_context():
    case = dict(get_memory_calibration_cases()[0])

    case["reference_context"] = "This should be a list."

    with pytest.raises(
        ValueError,
        match="reference_context",
    ):
        validate_memory_calibration_case(case)
