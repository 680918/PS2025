import pytest

from memory.memory_defense_dataset import (
    get_memory_defense_cases,
    validate_memory_defense_case,
)


def test_memory_defense_dataset_should_contain_four_cases():
    cases = get_memory_defense_cases()

    assert len(cases) == 4


def test_memory_defense_dataset_should_have_unique_case_ids():
    cases = get_memory_defense_cases()

    case_ids = [case["case_id"] for case in cases]

    assert len(case_ids) == len(set(case_ids))


def test_memory_defense_dataset_should_validate_all_cases():
    cases = get_memory_defense_cases()

    for case in cases:
        assert validate_memory_defense_case(case) is True


def test_memory_defense_dataset_should_cover_blocked_and_not_blocked():
    cases = get_memory_defense_cases()

    outcomes = {case["expected_defense"] for case in cases}

    assert outcomes == {
        "blocked",
        "not_blocked",
    }


def test_memory_defense_case_should_reject_invalid_expected_defense():
    case = dict(get_memory_defense_cases()[0])

    case["expected_defense"] = "unknown"

    with pytest.raises(
        ValueError,
        match="expected_defense",
    ):
        validate_memory_defense_case(case)
