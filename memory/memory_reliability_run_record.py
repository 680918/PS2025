from datetime import (
    datetime,
    timezone,
)


_SCHEMA_VERSION = 1

_TRACE_STAGES = (
    "candidates",
    "blocked_by_trust",
    "trusted_candidates",
    "not_selected_before_budget",
    "selected_before_budget",
    "removed_by_budget",
    "injected",
)


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_memory_reliability_run_record(
    run_id,
    trace,
    created_at=None,
):
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a non-empty string")

    if created_at is None:
        created_at = _utc_now_iso()

    record = {
        "schema_version": (_SCHEMA_VERSION),
        "run_id": run_id,
        "created_at": created_at,
    }

    for stage in _TRACE_STAGES:
        record[stage] = trace[stage]["total"]

    return record
