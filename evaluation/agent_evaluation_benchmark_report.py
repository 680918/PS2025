from pathlib import Path


def render_agent_evaluation_benchmark_report(
    benchmark_result,
):
    average_metrics = benchmark_result["average_metrics"]

    lines = [
        "Agent Evaluation Benchmark Report",
        "",
        f"Cases: {len(benchmark_result['cases'])}",
        "",
        "Average metrics:",
        (f"Goal alignment: {average_metrics['goal_alignment']:.4f}"),
        (f"Actionability: {average_metrics['actionability']:.4f}"),
        (f"Memory usage: {average_metrics['memory_usage']:.4f}"),
        (f"Knowledge usage: {average_metrics['knowledge_usage']:.4f}"),
        (f"Response policy: {average_metrics['response_policy']:.4f}"),
        (f"Overall score: {average_metrics['overall_score']:.4f}"),
    ]

    return "\n".join(lines)


def save_agent_evaluation_benchmark_report(
    benchmark_result,
    output_path,
):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = render_agent_evaluation_benchmark_report(benchmark_result)

    output_path.write_text(
        report,
        encoding="utf-8",
    )

    return output_path
