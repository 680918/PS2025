_METRICS_SCHEMA_VERSION = 1

_SUPPORTED_RECORD_SCHEMA_VERSION = 1

_METRIC_FIELDS = (
    "candidates",
    "blocked_by_trust",
    "trusted_candidates",
    "not_selected_before_budget",
    "selected_before_budget",
    "removed_by_budget",
    "injected",
)


def _safe_ratio(
    numerator,
    denominator,
):
    if denominator == 0:
        return 0.0

    return numerator / denominator


def _validate_funnel(
    record,
):
    if (
        record["candidates"]
        != record["blocked_by_trust"] + record["trusted_candidates"]
    ):
        raise ValueError("funnel invariant failed: candidates")

    if (
        record["trusted_candidates"]
        != record["not_selected_before_budget"] + record["selected_before_budget"]
    ):
        raise ValueError("funnel invariant failed: trusted_candidates")

    if (
        record["selected_before_budget"]
        != record["removed_by_budget"] + record["injected"]
    ):
        raise ValueError("funnel invariant failed: selected_before_budget")


def _validate_record(
    record,
):
    if record.get("schema_version") != _SUPPORTED_RECORD_SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")

    _validate_funnel(record)


def calculate_memory_reliability_metrics(
    records,
):
    totals = {field: 0 for field in _METRIC_FIELDS}

    for record in records:
        _validate_record(record)

        for field in _METRIC_FIELDS:
            totals[field] += record[field]

    run_count = len(records)

    return {
        "metrics_schema_version": (_METRICS_SCHEMA_VERSION),
        "run_count": run_count,
        "totals": totals,
        "averages": {
            "candidates_per_run": (
                _safe_ratio(
                    totals["candidates"],
                    run_count,
                )
            ),
            "injected_per_run": (
                _safe_ratio(
                    totals["injected"],
                    run_count,
                )
            ),
        },
        "rates": {
            "trust_block_rate": (
                _safe_ratio(
                    totals["blocked_by_trust"],
                    totals["candidates"],
                )
            ),
            "selection_drop_rate": (
                _safe_ratio(
                    totals["not_selected_before_budget"],
                    totals["trusted_candidates"],
                )
            ),
            "budget_drop_rate": (
                _safe_ratio(
                    totals["removed_by_budget"],
                    totals["selected_before_budget"],
                )
            ),
            "injection_rate": (
                _safe_ratio(
                    totals["injected"],
                    totals["candidates"],
                )
            ),
        },
    }
