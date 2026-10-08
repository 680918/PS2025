import pytest

from memory.memory_contribution_dataset import (
    get_memory_contribution_evaluation_cases,
    validate_memory_contribution_case,
)


def test_memory_contribution_dataset_should_expose_valid_unique_cases():
    cases = get_memory_contribution_evaluation_cases()

    assert len(cases) >= 3

    case_ids = [case["case_id"] for case in cases]

    assert len(case_ids) == len(set(case_ids))

    expected_effects = {case["expected_effect"] for case in cases}

    assert expected_effects == {
        "positive",
        "neutral",
        "negative",
    }

    for case in cases:
        assert validate_memory_contribution_case(case)
        assert isinstance(
            case["evaluation_criteria"],
            list,
        )
        assert case["evaluation_criteria"]


def test_memory_contribution_case_should_require_core_fields():
    invalid_case = {
        "case_id": "missing-query",
        "memory_context": [],
        "expected_effect": "neutral",
    }

    with pytest.raises(
        ValueError,
        match="missing required fields",
    ):
        validate_memory_contribution_case(invalid_case)


def test_memory_contribution_case_should_reject_unknown_effect():
    invalid_case = {
        "case_id": "unknown-effect",
        "query": "Explain Tool Calling",
        "memory_context": [],
        "expected_effect": "maybe",
        "evaluation_criteria": [
            "The answer should explain Tool Calling.",
        ],
    }

    with pytest.raises(
        ValueError,
        match="invalid expected_effect",
    ):
        validate_memory_contribution_case(invalid_case)


def test_memory_contribution_case_should_require_memory_list():
    invalid_case = {
        "case_id": "invalid-context",
        "query": "Explain Tool Calling",
        "memory_context": "not-a-list",
        "expected_effect": "neutral",
        "evaluation_criteria": [
            "The answer should explain Tool Calling.",
        ],
    }

    with pytest.raises(
        ValueError,
        match="memory_context must be a list",
    ):
        validate_memory_contribution_case(invalid_case)


def test_memory_contribution_case_should_require_evaluation_criteria_list():
    invalid_case = {
        "case_id": "invalid-criteria",
        "query": "Explain Tool Calling",
        "memory_context": [],
        "expected_effect": "neutral",
        "evaluation_criteria": "not-a-list",
    }

    with pytest.raises(
        ValueError,
        match="evaluation_criteria must be a non-empty list",
    ):
        validate_memory_contribution_case(invalid_case)


def test_memory_contribution_case_should_reject_empty_evaluation_criteria():
    invalid_case = {
        "case_id": "empty-criteria",
        "query": "Explain Tool Calling",
        "memory_context": [],
        "expected_effect": "neutral",
        "evaluation_criteria": [],
    }

    with pytest.raises(
        ValueError,
        match="evaluation_criteria must be a non-empty list",
    ):
        validate_memory_contribution_case(invalid_case)
