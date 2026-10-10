from memory.memory_reliability_run_record_store import (
    SQLiteMemoryReliabilityRunRecordStore,
)


def _record(
    *,
    run_id,
    created_at,
    candidates=8,
    blocked_by_trust=1,
    trusted_candidates=7,
    not_selected_before_budget=3,
    selected_before_budget=4,
    removed_by_budget=1,
    injected=3,
):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": created_at,
        "candidates": candidates,
        "blocked_by_trust": blocked_by_trust,
        "trusted_candidates": trusted_candidates,
        "not_selected_before_budget": (not_selected_before_budget),
        "selected_before_budget": (selected_before_budget),
        "removed_by_budget": (removed_by_budget),
        "injected": injected,
    }


def test_run_record_store_should_save_and_list_records(
    tmp_path,
):
    db_path = tmp_path / "memory_reliability.db"

    store = SQLiteMemoryReliabilityRunRecordStore(db_path)

    record = _record(
        run_id="run-001",
        created_at=("2026-10-09T22:00:00+00:00"),
    )

    store.save(record)

    assert store.list_all() == [record]


def test_run_record_store_should_persist_across_restart(
    tmp_path,
):
    db_path = tmp_path / "memory_reliability.db"

    first_store = SQLiteMemoryReliabilityRunRecordStore(db_path)

    first_store.save(
        _record(
            run_id="run-001",
            created_at=("2026-10-09T22:00:00+00:00"),
        )
    )

    second_store = SQLiteMemoryReliabilityRunRecordStore(db_path)

    records = second_store.list_all()

    assert len(records) == 1
    assert records[0]["run_id"] == "run-001"


def test_run_record_store_should_return_records_in_created_order(
    tmp_path,
):
    store = SQLiteMemoryReliabilityRunRecordStore(tmp_path / "memory_reliability.db")

    store.save(
        _record(
            run_id="run-002",
            created_at=("2026-10-09T23:00:00+00:00"),
        )
    )

    store.save(
        _record(
            run_id="run-001",
            created_at=("2026-10-09T22:00:00+00:00"),
        )
    )

    records = store.list_all()

    assert [record["run_id"] for record in records] == [
        "run-001",
        "run-002",
    ]


def test_run_record_store_should_return_empty_list_when_no_records(
    tmp_path,
):
    store = SQLiteMemoryReliabilityRunRecordStore(tmp_path / "memory_reliability.db")

    assert store.list_all() == []


def test_run_record_store_should_list_recent_records(
    tmp_path,
):
    store = SQLiteMemoryReliabilityRunRecordStore(tmp_path / "memory_reliability.db")

    store.save(
        _record(
            run_id="run-001",
            created_at=("2026-10-10T08:00:00+00:00"),
        )
    )

    store.save(
        _record(
            run_id="run-002",
            created_at=("2026-10-10T09:00:00+00:00"),
        )
    )

    store.save(
        _record(
            run_id="run-003",
            created_at=("2026-10-10T10:00:00+00:00"),
        )
    )

    records = store.list_recent(
        limit=2,
    )

    assert [record["run_id"] for record in records] == [
        "run-002",
        "run-003",
    ]


def test_run_record_store_should_reject_non_positive_recent_limit(
    tmp_path,
):
    store = SQLiteMemoryReliabilityRunRecordStore(tmp_path / "memory_reliability.db")

    for limit in (
        0,
        -1,
    ):
        try:
            store.list_recent(
                limit=limit,
            )
        except ValueError as error:
            assert "limit" in str(error)
        else:
            raise AssertionError("Expected ValueError")
