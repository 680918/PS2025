def evaluate_calibration_regression(
    current,
    baseline,
):
    regressions = []
    deltas = {}

    for metric_name, baseline_value in baseline.items():
        current_value = current[metric_name]

        deltas[metric_name] = current_value - baseline_value

        if current_value < baseline_value:
            regressions.append(metric_name)

    return {
        "passed": not regressions,
        "regressions": regressions,
        "baseline": baseline,
        "current": current,
        "deltas": deltas,
    }
