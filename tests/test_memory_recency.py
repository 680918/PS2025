import pytest

from datetime import datetime, timedelta, timezone
from memory.memory_recency import (
    calculate_recency_score,
)


def test_recent_memory_should_have_full_recency_score():
    reference_time = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    score = calculate_recency_score(
        updated_at=reference_time,
        reference_time=reference_time,
    )

    assert score == 1.0


def test_older_memory_should_have_lower_recency_score():
    reference_time = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    updated_at = reference_time - timedelta(
        days=30,
    )

    score = calculate_recency_score(
        updated_at=updated_at,
        reference_time=reference_time,
    )

    assert 0.0 <= score < 1.0


def test_memory_at_half_life_should_have_half_recency_score():
    reference_time = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    updated_at = reference_time - timedelta(
        days=30,
    )

    score = calculate_recency_score(
        updated_at=updated_at,
        reference_time=reference_time,
    )

    assert score == pytest.approx(0.5)


def test_memory_at_two_half_lives_should_have_quarter_recency_score():
    reference_time = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    updated_at = reference_time - timedelta(
        days=60,
    )

    score = calculate_recency_score(
        updated_at=updated_at,
        reference_time=reference_time,
    )

    assert score == pytest.approx(0.25)


def test_future_memory_should_be_capped_at_full_recency_score():
    reference_time = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    updated_at = reference_time + timedelta(
        days=1,
    )

    score = calculate_recency_score(
        updated_at=updated_at,
        reference_time=reference_time,
    )

    assert score == 1.0


def test_naive_updated_at_should_be_handled_safely():
    reference_time = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    updated_at = datetime(
        2026,
        9,
        7,
    )

    score = calculate_recency_score(
        updated_at=updated_at,
        reference_time=reference_time,
    )

    assert 0.0 <= score <= 1.0


def test_naive_reference_time_should_be_handled_safely():
    updated_at = datetime(
        2026,
        9,
        7,
        tzinfo=timezone.utc,
    )

    reference_time = datetime(
        2026,
        10,
        7,
    )

    score = calculate_recency_score(
        updated_at=updated_at,
        reference_time=reference_time,
    )

    assert 0.0 <= score <= 1.0


def test_missing_updated_at_should_return_zero_recency_score():
    reference_time = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    score = calculate_recency_score(
        updated_at=None,
        reference_time=reference_time,
    )

    assert score == 0.0


def test_missing_reference_time_should_raise_value_error():
    updated_at = datetime(
        2026,
        10,
        7,
        tzinfo=timezone.utc,
    )

    with pytest.raises(
        ValueError,
        match="reference_time is required",
    ):
        calculate_recency_score(
            updated_at=updated_at,
            reference_time=None,
        )
