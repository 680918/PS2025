_INTERPRETATION_SCHEMA_VERSION = 1

_RATE_SIGNAL_MAP = {
    "trust_block_rate": ("trust_filtering_changed"),
    "selection_drop_rate": ("pre_budget_selection_changed"),
    "budget_drop_rate": ("budget_pressure_changed"),
    "injection_rate": ("pipeline_yield_changed"),
}


def _direction(
    delta,
):
    if delta > 0:
        return "increased"

    if delta < 0:
        return "decreased"

    return "unchanged"


def interpret_memory_reliability_trend(
    trend,
):
    facts = []
    signals = []

    for metric, signal_name in _RATE_SIGNAL_MAP.items():
        previous = trend["previous"]["rates"][metric]

        recent = trend["recent"]["rates"][metric]

        delta = trend["deltas"]["rates"][metric]

        direction = _direction(delta)

        facts.append(
            {
                "metric": metric,
                "previous": previous,
                "recent": recent,
                "delta": delta,
                "direction": direction,
            }
        )

        if direction != "unchanged":
            signals.append(
                {
                    "signal": signal_name,
                    "metric": metric,
                    "direction": direction,
                }
            )

    return {
        "interpretation_schema_version": (_INTERPRETATION_SCHEMA_VERSION),
        "window_size": trend["window_size"],
        "facts": facts,
        "signals": signals,
    }
