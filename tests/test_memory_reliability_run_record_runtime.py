from memory.memory_reliability_run_record_runtime import (
    create_user_memory_reliability_run_record_store,
    open_user_memory_reliability_run_record_store,
)


def _record(
    run_id,
):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": ("2026-10-10T08:00:00+00:00"),
        "candidates": 3,
        "blocked_by_trust": 1,
        "trusted_candidates": 2,
        "not_selected_before_budget": 1,
        "selected_before_budget": 1,
        "removed_by_budget": 0,
        "injected": 1,
    }


def test_user_reliability_stores_should_isolate_records(
    tmp_path,
):
    user_a_store = create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user_a",
    )

    user_b_store = create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user_b",
    )

    user_a_store.save(_record("run-a"))

    assert [record["run_id"] for record in user_a_store.list_all()] == [
        "run-a",
    ]

    assert user_b_store.list_all() == []


def test_same_user_reliability_store_should_persist_across_restart(
    tmp_path,
):
    first_store = create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user_a",
    )

    first_store.save(_record("run-001"))

    second_store = create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user_a",
    )

    records = second_store.list_all()

    assert len(records) == 1

    assert records[0]["run_id"] == "run-001"


def test_user_reliability_store_should_create_expected_directory(
    tmp_path,
):
    create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user_a",
    )

    expected_db_path = tmp_path / "memory_reliability" / "user_a.db"

    assert expected_db_path.exists()


def test_open_user_reliability_store_should_read_existing_database(
    tmp_path,
):
    created_store = create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user_a",
    )

    created_store.save(_record("run-001"))

    opened_store = open_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user_a",
    )

    records = opened_store.list_all()

    assert len(records) == 1
    assert records[0]["run_id"] == "run-001"


def test_open_user_reliability_store_should_reject_missing_database(
    tmp_path,
):
    try:
        open_user_memory_reliability_run_record_store(
            database_dir=tmp_path,
            user_id="missing-user",
        )
    except FileNotFoundError as error:
        assert "missing-user" in str(error)
    else:
        raise AssertionError("Expected FileNotFoundError")

    assert not (tmp_path / "memory_reliability" / "missing-user.db").exists()
