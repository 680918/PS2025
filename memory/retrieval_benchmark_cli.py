def format_benchmark_report(
    report,
):
    lines = []

    lines.append("Memory Retrieval Benchmark")

    lines.append("")

    cases = report.get(
        "cases",
        {},
    )

    for case_name, case_data in cases.items():
        lines.append(f"Case: {case_name}")

        for k, metrics in case_data["metrics"].items():
            lines.append(
                f"K={k} "
                f"F1: {metrics['f1_at_k']:.2f} "
                f"Retrieved: {metrics.get('retrieved_count', 0)} "
                f"Compression: {metrics.get('compression_ratio', 0):.2f} "
                f"Gap: {metrics.get('score_gap', 0):.2f}"
            )

            if metrics.get("top_memory_key") is not None:
                lines.append(
                    f"  Top: {metrics['top_memory_key']} "
                    f"({metrics.get('top_score', 0):.2f})"
                )

            if metrics.get("second_memory_key") is not None:
                lines.append(
                    f"  Second: {metrics['second_memory_key']} "
                    f"({metrics.get('second_score', 0):.2f})"
                )

        lines.append("")

    lines.append("Average F1")

    for k, f1 in report.get(
        "average_f1_by_k",
        {},
    ).items():
        lines.append(f"K={k}: {f1:.2f}")

    lines.append("")

    lines.append("Average Retrieved Count")

    for k, count in report.get(
        "average_retrieved_count_by_k",
        {},
    ).items():
        lines.append(f"K={k}: {count:.2f}")

    lines.append("")

    lines.append("Average Compression Ratio")

    for k, ratio in report.get(
        "average_compression_ratio_by_k",
        {},
    ).items():
        lines.append(f"K={k}: {ratio:.2f}")

    return "\n".join(lines)
