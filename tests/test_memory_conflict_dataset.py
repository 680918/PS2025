import pytest

from memory.memory_conflict_dataset import (
    get_memory_conflict_cases,
    validate_memory_conflict_case,
)


def test_memory_conflict_dataset_should_contain_five_cases():
    cases = get_memory_conflict_cases()

    assert len(cases) == 5


def test_memory_conflict_dataset_should_have_unique_case_ids():
    cases = get_memory_conflict_cases()

    case_ids = [case["case_id"] for case in cases]

    assert len(case_ids) == len(set(case_ids))


def test_memory_conflict_dataset_should_validate_all_cases():
    cases = get_memory_conflict_cases()

    for case in cases:
        assert validate_memory_conflict_case(case) is True


def test_memory_conflict_dataset_should_cover_conflict_and_non_conflict():
    cases = get_memory_conflict_cases()

    outcomes = {case["expected_conflict"] for case in cases}

    assert outcomes == {
        True,
        False,
    }


def test_memory_conflict_case_should_reject_invalid_expected_conflict():
    case = dict(get_memory_conflict_cases()[0])

    case["expected_conflict"] = "yes"

    with pytest.raises(
        ValueError,
        match="expected_conflict",
    ):
        validate_memory_conflict_case(case)
