from pathlib import Path


def render_agent_evaluation_comparison(
    comparison,
):
    lines = [
        "Agent Evaluation Regression Comparison",
        "",
        f"Status: {comparison['status']}",
        (f"Goal alignment delta: {comparison['goal_alignment_delta']:+.4f}"),
        (f"Actionability delta: {comparison['actionability_delta']:+.4f}"),
        (f"Memory usage delta: {comparison['memory_usage_delta']:+.4f}"),
        (f"Knowledge usage delta: {comparison['knowledge_usage_delta']:+.4f}"),
        (f"Response policy delta: {comparison['response_policy_delta']:+.4f}"),
        (f"Overall score delta: {comparison['overall_score_delta']:+.4f}"),
    ]

    return "\n".join(lines)


def save_agent_evaluation_comparison_report(
    comparison,
    output_path,
):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        render_agent_evaluation_comparison(comparison),
        encoding="utf-8",
    )

    return output_path
