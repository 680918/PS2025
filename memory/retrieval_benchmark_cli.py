def format_benchmark_report(
    report,
):
    lines = []

    lines.append("Memory Retrieval Benchmark")

    lines.append("")

    lines.append("Average F1")

    for k, f1 in report.get(
        "average_f1_by_k",
        {},
    ).items():
        lines.append(f"K={k}: {f1:.2f}")

    return "\n".join(lines)
