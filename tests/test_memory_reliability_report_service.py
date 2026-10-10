from memory.memory_reliability_report_service import (
    build_memory_reliability_report,
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


def test_report_service_should_build_metrics_from_store():
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

    class FakeStore:
        def list_all(self):
            return records

    report = build_memory_reliability_report(
        store=FakeStore(),
    )

    assert report["run_count"] == 2

    assert report["totals"]["candidates"] == 10

    assert report["totals"]["injected"] == 4

    assert report["rates"]["trust_block_rate"] == 0.1


def test_report_service_should_handle_empty_store():
    class FakeStore:
        def list_all(self):
            return []

    report = build_memory_reliability_report(
        store=FakeStore(),
    )

    assert report["run_count"] == 0

    assert report["totals"]["candidates"] == 0

    assert report["rates"]["injection_rate"] == 0.0


def test_report_service_should_read_store_once():
    calls = {
        "list_all": 0,
    }

    class FakeStore:
        def list_all(self):
            calls["list_all"] += 1

            return []

    build_memory_reliability_report(
        store=FakeStore(),
    )

    assert calls["list_all"] == 1


def test_report_service_should_use_recent_records_when_limit_is_provided():
    calls = {
        "list_all": 0,
        "list_recent": [],
    }

    recent_records = [
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

    class FakeStore:
        def list_all(self):
            calls["list_all"] += 1
            return []

        def list_recent(
            self,
            limit,
        ):
            calls["list_recent"].append(limit)

            return recent_records

    report = build_memory_reliability_report(
        store=FakeStore(),
        limit=1,
    )

    assert calls["list_all"] == 0

    assert calls["list_recent"] == [
        1,
    ]

    assert report["run_count"] == 1

    assert report["totals"]["candidates"] == 2


def test_report_service_should_use_all_records_when_limit_is_none():
    calls = {
        "list_all": 0,
        "list_recent": 0,
    }

    class FakeStore:
        def list_all(self):
            calls["list_all"] += 1
            return []

        def list_recent(
            self,
            limit,
        ):
            calls["list_recent"] += 1

            return []

    build_memory_reliability_report(
        store=FakeStore(),
        limit=None,
    )

    assert calls["list_all"] == 1

    assert calls["list_recent"] == 0
