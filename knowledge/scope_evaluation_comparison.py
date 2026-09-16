from pathlib import Path


def compare_scope_evaluation_reports(
    previous_report,
    current_report,
    tolerance=1e-9,
):
    previous_summary = previous_report["summary"]
    current_summary = current_report["summary"]

    pass_rate_delta = current_summary["pass_rate"] - previous_summary["pass_rate"]

    precision_delta = (
        current_summary["average_precision"] - previous_summary["average_precision"]
    )

    recall_delta = (
        current_summary["average_recall"] - previous_summary["average_recall"]
    )

    f1_delta = current_summary["average_f1"] - previous_summary["average_f1"]

    if f1_delta > tolerance:
        status = "improved"
    elif f1_delta < -tolerance:
        status = "regressed"
    else:
        status = "unchanged"

    return {
        "pass_rate_delta": pass_rate_delta,
        "precision_delta": precision_delta,
        "recall_delta": recall_delta,
        "f1_delta": f1_delta,
        "status": status,
    }


def render_scope_evaluation_comparison(
    comparison,
):
    lines = [
        "Knowledge Scope Regression Comparison",
        "",
        f"Status: {comparison['status']}",
        (f"Pass rate delta: {comparison['pass_rate_delta']:+.4f}"),
        (f"Precision delta: {comparison['precision_delta']:+.4f}"),
        (f"Recall delta: {comparison['recall_delta']:+.4f}"),
        (f"F1 delta: {comparison['f1_delta']:+.4f}"),
    ]

    return "\n".join(lines)


def save_scope_evaluation_comparison(
    comparison,
    output_path,
):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    text = render_scope_evaluation_comparison(
        comparison,
    )

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    return output_path
