from memory.memory_reliability_trend_interpretation import (
    interpret_memory_reliability_trend,
)


def _trend(
    *,
    trust_block_delta=0.0,
    selection_drop_delta=0.0,
    budget_drop_delta=0.0,
    injection_delta=0.0,
):
    return {
        "trend_schema_version": 1,
        "window_size": 5,
        "previous": {
            "rates": {
                "trust_block_rate": 0.1,
                "selection_drop_rate": 0.2,
                "budget_drop_rate": 0.1,
                "injection_rate": 0.5,
            },
        },
        "recent": {
            "rates": {
                "trust_block_rate": (0.1 + trust_block_delta),
                "selection_drop_rate": (0.2 + selection_drop_delta),
                "budget_drop_rate": (0.1 + budget_drop_delta),
                "injection_rate": (0.5 + injection_delta),
            },
        },
        "deltas": {
            "rates": {
                "trust_block_rate": (trust_block_delta),
                "selection_drop_rate": (selection_drop_delta),
                "budget_drop_rate": (budget_drop_delta),
                "injection_rate": (injection_delta),
            },
            "averages": {},
        },
    }


def test_interpretation_should_report_rate_change_facts():
    result = interpret_memory_reliability_trend(
        _trend(
            injection_delta=0.2,
        )
    )

    fact = next(fact for fact in result["facts"] if fact["metric"] == "injection_rate")

    assert fact == {
        "metric": "injection_rate",
        "previous": 0.5,
        "recent": 0.7,
        "delta": 0.2,
        "direction": "increased",
    }


def test_interpretation_should_report_decreased_direction():
    result = interpret_memory_reliability_trend(
        _trend(
            trust_block_delta=-0.05,
        )
    )

    fact = next(
        fact for fact in result["facts"] if fact["metric"] == "trust_block_rate"
    )

    assert fact["direction"] == "decreased"


def test_interpretation_should_create_semantic_investigation_signals():
    result = interpret_memory_reliability_trend(
        _trend(
            selection_drop_delta=0.1,
            budget_drop_delta=-0.05,
        )
    )

    assert {
        "signal": ("pre_budget_selection_changed"),
        "metric": "selection_drop_rate",
        "direction": "increased",
    } in result["signals"]

    assert {
        "signal": "budget_pressure_changed",
        "metric": "budget_drop_rate",
        "direction": "decreased",
    } in result["signals"]


def test_interpretation_should_not_signal_unchanged_rates():
    result = interpret_memory_reliability_trend(_trend())

    assert result["signals"] == []


def test_interpretation_should_preserve_neutral_semantics():
    result = interpret_memory_reliability_trend(
        _trend(
            injection_delta=0.2,
        )
    )

    assert "status" not in result
    assert "improved" not in str(result)
    assert "regressed" not in str(result)
