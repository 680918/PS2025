import pytest

from memory.memory_reliability_run_record import (
    build_memory_reliability_run_record,
)


def _stage(
    total,
):
    return {
        "total": total,
        "count_by_type": {
            "profile": 0,
            "skill": 0,
            "learning": total,
            "project": 0,
            "experience": 0,
        },
        "memory_keys_by_type": {
            "profile": [],
            "skill": [],
            "learning": [f"memory-{index}" for index in range(total)],
            "project": [],
            "experience": [],
        },
    }


def test_run_record_should_compress_reliability_trace_to_metrics():
    trace = {
        "candidates": _stage(8),
        "blocked_by_trust": _stage(1),
        "trusted_candidates": _stage(7),
        "not_selected_before_budget": (_stage(3)),
        "selected_before_budget": (_stage(4)),
        "removed_by_budget": _stage(1),
        "injected": _stage(3),
    }

    record = build_memory_reliability_run_record(
        run_id="run-123",
        trace=trace,
        created_at=("2026-10-09T22:00:00+00:00"),
    )

    assert record == {
        "schema_version": 1,
        "run_id": "run-123",
        "created_at": ("2026-10-09T22:00:00+00:00"),
        "candidates": 8,
        "blocked_by_trust": 1,
        "trusted_candidates": 7,
        "not_selected_before_budget": 3,
        "selected_before_budget": 4,
        "removed_by_budget": 1,
        "injected": 3,
    }


def test_run_record_should_not_copy_memory_keys():
    trace = {
        "candidates": _stage(2),
        "blocked_by_trust": _stage(0),
        "trusted_candidates": _stage(2),
        "not_selected_before_budget": (_stage(1)),
        "selected_before_budget": (_stage(1)),
        "removed_by_budget": _stage(0),
        "injected": _stage(1),
    }

    record = build_memory_reliability_run_record(
        run_id="run-456",
        trace=trace,
        created_at=("2026-10-09T22:00:00+00:00"),
    )

    assert "memory_keys_by_type" not in record
    assert "count_by_type" not in record

    assert all("memory-" not in str(value) for value in record.values())


def test_run_record_should_reject_empty_run_id():
    trace = {
        "candidates": _stage(0),
        "blocked_by_trust": _stage(0),
        "trusted_candidates": _stage(0),
        "not_selected_before_budget": (_stage(0)),
        "selected_before_budget": (_stage(0)),
        "removed_by_budget": _stage(0),
        "injected": _stage(0),
    }

    with pytest.raises(
        ValueError,
        match="run_id",
    ):
        build_memory_reliability_run_record(
            run_id="",
            trace=trace,
            created_at=("2026-10-09T22:00:00+00:00"),
        )
