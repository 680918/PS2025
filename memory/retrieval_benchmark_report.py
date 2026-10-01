def summarize_benchmark_results(
    results,
):
    if not results:
        return {
            "cases": {},
            "average_f1_by_k": {},
        }

    totals = {}
    counts = {}

    cases = {}

    for result in results:
        case_name = result["name"]

        cases[case_name] = {
            "metrics": result["metrics"],
        }

        for k, metrics in result["metrics"].items():
            if k not in totals:
                totals[k] = 0.0
                counts[k] = 0

            totals[k] += metrics["f1_at_k"]
            counts[k] += 1

    average_f1_by_k = {k: totals[k] / counts[k] for k in totals}

    return {
        "cases": cases,
        "average_f1_by_k": average_f1_by_k,
    }
