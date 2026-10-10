_INTERPRETATION_SCHEMA_VERSION = 1

_RATE_SIGNAL_MAP = {
    "trust_block_rate": ("trust_filtering_changed"),
    "selection_drop_rate": ("pre_budget_selection_changed"),
    "budget_drop_rate": ("budget_pressure_changed"),
    "injection_rate": ("pipeline_yield_changed"),
}

_RATE_DENOMINATOR_MAP = {
    "trust_block_rate": "candidates",
    "selection_drop_rate": ("trusted_candidates"),
    "budget_drop_rate": ("selected_before_budget"),
    "injection_rate": "candidates",
}


def _direction(
    delta,
):
    if delta > 0:
        return "increased"

    if delta < 0:
        return "decreased"

    return "unchanged"


def _is_rate_comparable(
    trend,
    metric,
):
    denominator = _RATE_DENOMINATOR_MAP[metric]

    previous_denominator = trend["previous"]["totals"][denominator]

    recent_denominator = trend["recent"]["totals"][denominator]

    return previous_denominator > 0 and recent_denominator > 0


def interpret_memory_reliability_trend(
    trend,
):
    facts = []
    signals = []

    for metric, signal_name in _RATE_SIGNAL_MAP.items():
        previous = trend["previous"]["rates"][metric]

        recent = trend["recent"]["rates"][metric]

        delta = trend["deltas"]["rates"][metric]

        comparable = _is_rate_comparable(
            trend,
            metric,
        )

        if comparable:
            direction = _direction(delta)
        else:
            direction = "not_comparable"

        facts.append(
            {
                "metric": metric,
                "previous": previous,
                "recent": recent,
                "delta": delta,
                "direction": direction,
                "comparable": comparable,
            }
        )

        if comparable and direction != "unchanged":
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
