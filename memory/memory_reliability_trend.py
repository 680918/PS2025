from memory.memory_reliability_metrics import (
    calculate_memory_reliability_metrics,
)


_TREND_SCHEMA_VERSION = 1

_RATE_FIELDS = (
    "trust_block_rate",
    "selection_drop_rate",
    "budget_drop_rate",
    "injection_rate",
)

_AVERAGE_FIELDS = (
    "candidates_per_run",
    "injected_per_run",
)


def _calculate_deltas(
    previous,
    recent,
):
    return {
        "rates": {
            field: (recent["rates"][field] - previous["rates"][field])
            for field in _RATE_FIELDS
        },
        "averages": {
            field: (recent["averages"][field] - previous["averages"][field])
            for field in _AVERAGE_FIELDS
        },
    }


def compare_memory_reliability_trends(
    store,
    window_size,
):
    if window_size <= 0:
        raise ValueError("window_size must be positive")

    records = store.list_recent(
        limit=window_size * 2,
    )

    if len(records) < window_size * 2:
        raise ValueError("not enough records for complete trend windows")

    previous_records = records[:window_size]

    recent_records = records[window_size:]

    previous = calculate_memory_reliability_metrics(previous_records)

    recent = calculate_memory_reliability_metrics(recent_records)

    return {
        "trend_schema_version": (_TREND_SCHEMA_VERSION),
        "window_size": window_size,
        "previous": previous,
        "recent": recent,
        "deltas": _calculate_deltas(
            previous,
            recent,
        ),
    }
