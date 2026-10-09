import pytest

from memory.memory_conflict_resolution_dataset import (
    get_memory_conflict_resolution_cases,
    validate_memory_conflict_resolution_case,
)


def test_conflict_resolution_dataset_should_contain_seven_cases():
    cases = get_memory_conflict_resolution_cases()

    assert len(cases) == 7


def test_conflict_resolution_dataset_should_have_six_baseline_and_one_challenge():
    cases = get_memory_conflict_resolution_cases()

    categories = [case["category"] for case in cases]

    assert categories.count("baseline") == 6
    assert categories.count("challenge") == 1


def test_conflict_resolution_dataset_should_have_unique_case_ids():
    cases = get_memory_conflict_resolution_cases()

    case_ids = [case["case_id"] for case in cases]

    assert len(case_ids) == len(set(case_ids))


def test_conflict_resolution_dataset_should_validate_all_cases():
    cases = get_memory_conflict_resolution_cases()

    for case in cases:
        assert validate_memory_conflict_resolution_case(case) is True


def test_conflict_resolution_case_should_reject_invalid_resolution():
    case = dict(get_memory_conflict_resolution_cases()[0])

    case["expected_resolution"] = "unknown"

    with pytest.raises(
        ValueError,
        match="expected_resolution",
    ):
        validate_memory_conflict_resolution_case(case)
