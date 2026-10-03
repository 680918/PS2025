def summarize_benchmark_results(
    results,
):
    if not results:
        return {
            "cases": {},
            "average_f1_by_k": {},
            "average_retrieved_count_by_k": {},
            "average_compression_ratio_by_k": {},
        }

    f1_totals = {}
    f1_counts = {}

    retrieved_totals = {}
    retrieved_counts = {}

    compression_totals = {}
    compression_counts = {}

    cases = {}

    for result in results:
        case_name = result["name"]

        cases[case_name] = {
            "metrics": result["metrics"],
        }

        for k, metrics in result["metrics"].items():
            if k not in f1_totals:
                f1_totals[k] = 0.0
                f1_counts[k] = 0

            f1_totals[k] += metrics["f1_at_k"]
            f1_counts[k] += 1

            if "retrieved_count" in metrics:
                if k not in retrieved_totals:
                    retrieved_totals[k] = 0.0
                    retrieved_counts[k] = 0

                retrieved_totals[k] += metrics["retrieved_count"]
                retrieved_counts[k] += 1

            if "compression_ratio" in metrics:
                if k not in compression_totals:
                    compression_totals[k] = 0.0
                    compression_counts[k] = 0

                compression_totals[k] += metrics["compression_ratio"]
                compression_counts[k] += 1

    average_f1_by_k = {k: f1_totals[k] / f1_counts[k] for k in f1_totals}

    average_retrieved_count_by_k = {
        k: retrieved_totals[k] / retrieved_counts[k] for k in retrieved_totals
    }

    average_compression_ratio_by_k = {
        k: compression_totals[k] / compression_counts[k] for k in compression_totals
    }

    return {
        "cases": cases,
        "average_f1_by_k": average_f1_by_k,
        "average_retrieved_count_by_k": (average_retrieved_count_by_k),
        "average_compression_ratio_by_k": (average_compression_ratio_by_k),
    }
