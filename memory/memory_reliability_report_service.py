from memory.memory_reliability_metrics import (
    calculate_memory_reliability_metrics,
)


def build_memory_reliability_report(
    store,
    limit=None,
):
    if limit is None:
        records = store.list_all()
    else:
        records = store.list_recent(
            limit=limit,
        )

    return calculate_memory_reliability_metrics(records)
