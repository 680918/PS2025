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
            lines.append(f"K={k} F1: {metrics['f1_at_k']:.2f}")

        lines.append("")

    lines.append("Average F1")

    for k, f1 in report.get(
        "average_f1_by_k",
        {},
    ).items():
        lines.append(f"K={k}: {f1:.2f}")

    return "\n".join(lines)
