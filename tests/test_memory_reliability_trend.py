import pytest

from memory.memory_reliability_trend import (
    compare_memory_reliability_trends,
)


def _record(
    *,
    run_id,
    candidates,
    blocked_by_trust,
    trusted_candidates,
    not_selected_before_budget,
    selected_before_budget,
    removed_by_budget,
    injected,
):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": ("2026-10-10T08:00:00+00:00"),
        "candidates": candidates,
        "blocked_by_trust": (blocked_by_trust),
        "trusted_candidates": (trusted_candidates),
        "not_selected_before_budget": (not_selected_before_budget),
        "selected_before_budget": (selected_before_budget),
        "removed_by_budget": (removed_by_budget),
        "injected": injected,
    }


def test_trend_should_compare_previous_and_recent_windows():
    records = [
        _record(
            run_id="run-001",
            candidates=10,
            blocked_by_trust=2,
            trusted_candidates=8,
            not_selected_before_budget=4,
            selected_before_budget=4,
            removed_by_budget=2,
            injected=2,
        ),
        _record(
            run_id="run-002",
            candidates=10,
            blocked_by_trust=2,
            trusted_candidates=8,
            not_selected_before_budget=4,
            selected_before_budget=4,
            removed_by_budget=2,
            injected=2,
        ),
        _record(
            run_id="run-003",
            candidates=10,
            blocked_by_trust=1,
            trusted_candidates=9,
            not_selected_before_budget=3,
            selected_before_budget=6,
            removed_by_budget=1,
            injected=5,
        ),
        _record(
            run_id="run-004",
            candidates=10,
            blocked_by_trust=1,
            trusted_candidates=9,
            not_selected_before_budget=3,
            selected_before_budget=6,
            removed_by_budget=1,
            injected=5,
        ),
    ]

    class FakeStore:
        def list_recent(
            self,
            limit,
        ):
            assert limit == 4
            return records

    result = compare_memory_reliability_trends(
        store=FakeStore(),
        window_size=2,
    )

    assert result["trend_schema_version"] == 1

    assert result["window_size"] == 2

    assert result["previous"]["run_count"] == 2

    assert result["recent"]["run_count"] == 2

    assert result["previous"]["rates"]["injection_rate"] == pytest.approx(0.2)

    assert result["recent"]["rates"]["injection_rate"] == pytest.approx(0.5)

    assert result["deltas"]["rates"]["injection_rate"] == pytest.approx(0.3)


def test_trend_should_calculate_rate_deltas():
    records = [
        _record(
            run_id="run-001",
            candidates=10,
            blocked_by_trust=2,
            trusted_candidates=8,
            not_selected_before_budget=4,
            selected_before_budget=4,
            removed_by_budget=2,
            injected=2,
        ),
        _record(
            run_id="run-002",
            candidates=10,
            blocked_by_trust=1,
            trusted_candidates=9,
            not_selected_before_budget=3,
            selected_before_budget=6,
            removed_by_budget=1,
            injected=5,
        ),
    ]

    class FakeStore:
        def list_recent(
            self,
            limit,
        ):
            return records

    result = compare_memory_reliability_trends(
        store=FakeStore(),
        window_size=1,
    )

    assert result["deltas"]["rates"]["trust_block_rate"] == pytest.approx(-0.1)

    assert result["deltas"]["rates"]["injection_rate"] == pytest.approx(0.3)


def test_trend_should_reject_incomplete_windows():
    class FakeStore:
        def list_recent(
            self,
            limit,
        ):
            return [
                _record(
                    run_id="run-001",
                    candidates=1,
                    blocked_by_trust=0,
                    trusted_candidates=1,
                    not_selected_before_budget=0,
                    selected_before_budget=1,
                    removed_by_budget=0,
                    injected=1,
                ),
            ]

    with pytest.raises(
        ValueError,
        match="not enough",
    ):
        compare_memory_reliability_trends(
            store=FakeStore(),
            window_size=2,
        )


def test_trend_should_reject_non_positive_window_size():
    class FakeStore:
        def list_recent(
            self,
            limit,
        ):
            return []

    with pytest.raises(
        ValueError,
        match="window_size",
    ):
        compare_memory_reliability_trends(
            store=FakeStore(),
            window_size=0,
        )
