import pytest

from memory.memory_reliability_metrics import (
    calculate_memory_reliability_metrics,
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


def test_reliability_metrics_should_aggregate_run_records():
    records = [
        _record(
            run_id="run-001",
            candidates=8,
            blocked_by_trust=1,
            trusted_candidates=7,
            not_selected_before_budget=3,
            selected_before_budget=4,
            removed_by_budget=1,
            injected=3,
        ),
        _record(
            run_id="run-002",
            candidates=2,
            blocked_by_trust=0,
            trusted_candidates=2,
            not_selected_before_budget=1,
            selected_before_budget=1,
            removed_by_budget=0,
            injected=1,
        ),
    ]

    metrics = calculate_memory_reliability_metrics(records)

    assert metrics["metrics_schema_version"] == 1

    assert metrics["run_count"] == 2

    assert metrics["totals"] == {
        "candidates": 10,
        "blocked_by_trust": 1,
        "trusted_candidates": 9,
        "not_selected_before_budget": 4,
        "selected_before_budget": 5,
        "removed_by_budget": 1,
        "injected": 4,
    }

    assert metrics["averages"]["candidates_per_run"] == pytest.approx(5.0)

    assert metrics["averages"]["injected_per_run"] == pytest.approx(2.0)

    assert metrics["rates"]["trust_block_rate"] == pytest.approx(0.1)

    assert metrics["rates"]["selection_drop_rate"] == pytest.approx(4 / 9)

    assert metrics["rates"]["budget_drop_rate"] == pytest.approx(0.2)

    assert metrics["rates"]["injection_rate"] == pytest.approx(0.4)


def test_reliability_metrics_should_handle_empty_records():
    metrics = calculate_memory_reliability_metrics([])

    assert metrics["run_count"] == 0

    assert metrics["averages"] == {
        "candidates_per_run": 0.0,
        "injected_per_run": 0.0,
    }

    assert metrics["rates"] == {
        "trust_block_rate": 0.0,
        "selection_drop_rate": 0.0,
        "budget_drop_rate": 0.0,
        "injection_rate": 0.0,
    }


def test_reliability_metrics_should_handle_zero_denominators():
    records = [
        _record(
            run_id="run-empty",
            candidates=0,
            blocked_by_trust=0,
            trusted_candidates=0,
            not_selected_before_budget=0,
            selected_before_budget=0,
            removed_by_budget=0,
            injected=0,
        ),
    ]

    metrics = calculate_memory_reliability_metrics(records)

    assert metrics["rates"] == {
        "trust_block_rate": 0.0,
        "selection_drop_rate": 0.0,
        "budget_drop_rate": 0.0,
        "injection_rate": 0.0,
    }


def test_reliability_metrics_should_reject_broken_funnel_record():
    records = [
        _record(
            run_id="broken-run",
            candidates=8,
            blocked_by_trust=1,
            trusted_candidates=6,
            not_selected_before_budget=2,
            selected_before_budget=4,
            removed_by_budget=1,
            injected=3,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="funnel invariant",
    ):
        calculate_memory_reliability_metrics(records)


def test_reliability_metrics_should_reject_unsupported_record_schema():
    record = _record(
        run_id="run-v2",
        candidates=1,
        blocked_by_trust=0,
        trusted_candidates=1,
        not_selected_before_budget=0,
        selected_before_budget=1,
        removed_by_budget=0,
        injected=1,
    )

    record["schema_version"] = 2

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        calculate_memory_reliability_metrics([record])
