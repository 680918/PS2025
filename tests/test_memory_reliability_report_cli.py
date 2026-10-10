import scripts.run_memory_reliability_report as cli

from memory.memory_reliability_run_record_runtime import (
    create_user_memory_reliability_run_record_store,
)


def test_report_cli_should_load_user_store_and_print_report(
    tmp_path,
    monkeypatch,
    capsys,
):
    captured = {}

    fake_store = object()

    def fake_create_store(
        database_dir,
        user_id,
    ):
        captured["database_dir"] = database_dir
        captured["user_id"] = user_id

        return fake_store

    def fake_build_report(
        store,
        limit=None,
    ):
        captured["store"] = store
        captured["limit"] = limit

        return {
            "metrics_schema_version": 1,
            "run_count": 20,
            "totals": {
                "candidates": 128,
                "blocked_by_trust": 6,
                "trusted_candidates": 122,
                "not_selected_before_budget": 59,
                "selected_before_budget": 63,
                "removed_by_budget": 5,
                "injected": 58,
            },
            "averages": {
                "candidates_per_run": 6.4,
                "injected_per_run": 2.9,
            },
            "rates": {
                "trust_block_rate": 0.047,
                "selection_drop_rate": 0.484,
                "budget_drop_rate": 0.079,
                "injection_rate": 0.453,
            },
        }

    monkeypatch.setattr(
        cli,
        ("open_user_memory_reliability_run_record_store"),
        fake_create_store,
    )

    monkeypatch.setattr(
        cli,
        "build_memory_reliability_report",
        fake_build_report,
    )

    cli.main(
        [
            "--database-dir",
            str(tmp_path),
            "--user-id",
            "user-123",
            "--limit",
            "20",
        ]
    )

    output = capsys.readouterr().out

    assert captured["database_dir"] == str(tmp_path)

    assert captured["user_id"] == "user-123"

    assert captured["store"] is fake_store

    assert captured["limit"] == 20

    assert "Memory Reliability Report" in output

    assert "Runs: 20" in output

    assert "Average candidates/run: 6.40" in output

    assert "Average injected/run:   2.90" in output

    assert "Trust block rate:       4.70%" in output

    assert "Selection drop rate:   48.40%" in output

    assert "Budget drop rate:       7.90%" in output

    assert "Injection rate:        45.30%" in output


def _record(
    *,
    run_id,
    created_at,
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
        "created_at": created_at,
        "candidates": candidates,
        "blocked_by_trust": (blocked_by_trust),
        "trusted_candidates": (trusted_candidates),
        "not_selected_before_budget": (not_selected_before_budget),
        "selected_before_budget": (selected_before_budget),
        "removed_by_budget": (removed_by_budget),
        "injected": injected,
    }


def test_report_cli_should_read_real_sqlite_data(
    tmp_path,
    capsys,
):
    store = create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user-123",
    )

    store.save(
        _record(
            run_id="run-001",
            created_at=("2026-10-10T08:00:00+00:00"),
            candidates=10,
            blocked_by_trust=2,
            trusted_candidates=8,
            not_selected_before_budget=4,
            selected_before_budget=4,
            removed_by_budget=1,
            injected=3,
        )
    )

    store.save(
        _record(
            run_id="run-002",
            created_at=("2026-10-10T09:00:00+00:00"),
            candidates=10,
            blocked_by_trust=0,
            trusted_candidates=10,
            not_selected_before_budget=5,
            selected_before_budget=5,
            removed_by_budget=0,
            injected=5,
        )
    )

    cli.main(
        [
            "--database-dir",
            str(tmp_path),
            "--user-id",
            "user-123",
        ]
    )

    output = capsys.readouterr().out

    assert "Runs: 2" in output

    assert "Average candidates/run: 10.00" in output

    assert "Average injected/run:   4.00" in output

    assert "Trust block rate:       10.00%" in output

    assert "Selection drop rate:   50.00%" in output

    assert "Budget drop rate:       11.11%" in output

    assert "Injection rate:        40.00%" in output


def test_report_cli_should_apply_recent_limit_to_real_sqlite_data(
    tmp_path,
    capsys,
):
    store = create_user_memory_reliability_run_record_store(
        database_dir=tmp_path,
        user_id="user-123",
    )

    store.save(
        _record(
            run_id="run-001",
            created_at=("2026-10-10T08:00:00+00:00"),
            candidates=10,
            blocked_by_trust=2,
            trusted_candidates=8,
            not_selected_before_budget=4,
            selected_before_budget=4,
            removed_by_budget=2,
            injected=2,
        )
    )

    store.save(
        _record(
            run_id="run-002",
            created_at=("2026-10-10T09:00:00+00:00"),
            candidates=4,
            blocked_by_trust=0,
            trusted_candidates=4,
            not_selected_before_budget=1,
            selected_before_budget=3,
            removed_by_budget=0,
            injected=3,
        )
    )

    cli.main(
        [
            "--database-dir",
            str(tmp_path),
            "--user-id",
            "user-123",
            "--limit",
            "1",
        ]
    )

    output = capsys.readouterr().out

    assert "Runs: 1" in output

    assert "Average candidates/run: 4.00" in output

    assert "Average injected/run:   3.00" in output

    assert "Injection rate:        75.00%" in output


def test_report_cli_should_print_trend_when_window_is_provided(
    tmp_path,
    monkeypatch,
    capsys,
):
    fake_store = object()

    monkeypatch.setattr(
        cli,
        ("open_user_memory_reliability_run_record_store"),
        lambda database_dir, user_id: fake_store,
    )

    monkeypatch.setattr(
        cli,
        "build_memory_reliability_report",
        lambda store, limit=None: {
            "metrics_schema_version": 1,
            "run_count": 20,
            "totals": {
                "candidates": 100,
                "blocked_by_trust": 10,
                "trusted_candidates": 90,
                "not_selected_before_budget": 40,
                "selected_before_budget": 50,
                "removed_by_budget": 10,
                "injected": 40,
            },
            "averages": {
                "candidates_per_run": 5.0,
                "injected_per_run": 2.0,
            },
            "rates": {
                "trust_block_rate": 0.1,
                "selection_drop_rate": 0.4,
                "budget_drop_rate": 0.2,
                "injection_rate": 0.4,
            },
        },
    )

    captured = {}

    def fake_compare(
        store,
        window_size,
    ):
        captured["store"] = store
        captured["window_size"] = window_size

        return {
            "trend_schema_version": 1,
            "window_size": 10,
            "previous": {},
            "recent": {},
            "deltas": {},
        }

    monkeypatch.setattr(
        cli,
        "compare_memory_reliability_trends",
        fake_compare,
    )

    monkeypatch.setattr(
        cli,
        "interpret_memory_reliability_trend",
        lambda trend: {
            "interpretation_schema_version": 1,
            "window_size": 10,
            "facts": [
                {
                    "metric": "injection_rate",
                    "previous": 0.30,
                    "recent": 0.45,
                    "delta": 0.15,
                    "direction": "increased",
                    "comparable": True,
                },
            ],
            "signals": [
                {
                    "signal": ("pipeline_yield_changed"),
                    "metric": ("injection_rate"),
                    "direction": ("increased"),
                },
            ],
        },
    )

    cli.main(
        [
            "--database-dir",
            str(tmp_path),
            "--user-id",
            "user-123",
            "--trend-window",
            "10",
        ]
    )

    output = capsys.readouterr().out

    assert captured["store"] is fake_store
    assert captured["window_size"] == 10

    assert "Memory Reliability Trend" in output

    assert "Window size: 10" in output

    assert "injection_rate: 30.00% -> 45.00% (+15.00%)" in output

    assert "pipeline_yield_changed" in output


def test_report_cli_should_not_build_trend_without_window(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        cli,
        ("open_user_memory_reliability_run_record_store"),
        lambda database_dir, user_id: object(),
    )

    monkeypatch.setattr(
        cli,
        "build_memory_reliability_report",
        lambda store, limit=None: {
            "metrics_schema_version": 1,
            "run_count": 0,
            "totals": {
                "candidates": 0,
                "blocked_by_trust": 0,
                "trusted_candidates": 0,
                "not_selected_before_budget": 0,
                "selected_before_budget": 0,
                "removed_by_budget": 0,
                "injected": 0,
            },
            "averages": {
                "candidates_per_run": 0.0,
                "injected_per_run": 0.0,
            },
            "rates": {
                "trust_block_rate": 0.0,
                "selection_drop_rate": 0.0,
                "budget_drop_rate": 0.0,
                "injection_rate": 0.0,
            },
        },
    )

    def fail_if_called(
        *args,
        **kwargs,
    ):
        raise AssertionError("trend should not be built")

    monkeypatch.setattr(
        cli,
        "compare_memory_reliability_trends",
        fail_if_called,
    )

    cli.main(
        [
            "--database-dir",
            str(tmp_path),
            "--user-id",
            "user-123",
        ]
    )


def test_report_cli_should_not_create_database_for_unknown_user(
    tmp_path,
):
    missing_db = tmp_path / "memory_reliability" / "missing-user.db"

    try:
        cli.main(
            [
                "--database-dir",
                str(tmp_path),
                "--user-id",
                "missing-user",
            ]
        )
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected FileNotFoundError")

    assert not missing_db.exists()
