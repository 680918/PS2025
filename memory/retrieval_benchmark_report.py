def summarize_benchmark_results(
    results,
):
    if not results:
        return {"average_f1_by_k": {}}

    totals = {}
    counts = {}

    for result in results:
        for k, metrics in result["metrics"].items():
            if k not in totals:
                totals[k] = 0.0
                counts[k] = 0

            totals[k] += metrics["f1_at_k"]
            counts[k] += 1

    average_f1_by_k = {k: totals[k] / counts[k] for k in totals}

    return {"average_f1_by_k": average_f1_by_k}
