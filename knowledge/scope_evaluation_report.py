from pathlib import Path


def build_scope_evaluation_report(
    batch_result,
    tuning_result,
):
    failed_cases = [
        result for result in batch_result["results"] if not result["passed"]
    ]

    case_count = batch_result["case_count"]
    passed_count = batch_result["passed_count"]

    if case_count == 0:
        pass_rate = 1.0
    else:
        pass_rate = passed_count / case_count

    return {
        "summary": {
            "case_count": case_count,
            "passed_count": passed_count,
            "failed_case_count": len(failed_cases),
            "pass_rate": pass_rate,
            "average_precision": batch_result["average_precision"],
            "average_recall": batch_result["average_recall"],
            "average_f1": batch_result["average_f1"],
        },
        "best_parameters": tuning_result["best_parameters"],
        "best_score": tuning_result["best_score"],
        "failed_cases": failed_cases,
    }


def render_scope_evaluation_report(report):
    summary = report["summary"]
    best_parameters = report["best_parameters"]
    failed_cases = report["failed_cases"]

    lines = [
        "Knowledge Scope Evaluation Report",
        "",
        f"Cases: {summary['case_count']}",
        f"Passed: {summary['passed_count']}",
        f"Failed: {summary['failed_case_count']}",
        f"Pass rate: {summary['pass_rate']:.2%}",
        f"Precision: {summary['average_precision']:.4f}",
        f"Recall: {summary['average_recall']:.4f}",
        f"F1: {summary['average_f1']:.4f}",
        "",
        "Best parameters:",
    ]

    if best_parameters is None:
        lines.append("None")
    else:
        lines.extend(
            [
                f"top_n: {best_parameters['top_n']}",
                f"min_score: {best_parameters['min_score']}",
                (f"min_relative_score: {best_parameters['min_relative_score']}"),
            ]
        )

    lines.append(f"Best score: {report['best_score']}")

    lines.append("")

    if not failed_cases:
        lines.append("Failed cases: None")
    else:
        lines.append("Failed cases:")

        for case in failed_cases:
            lines.append(f"- {case['name']}")
            lines.append(f"  expected: {case['expected_document_ids']}")
            lines.append(f"  actual: {case['actual_document_ids']}")

    return "\n".join(lines)


def save_scope_evaluation_report(
    report,
    output_path,
):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    text = render_scope_evaluation_report(report)

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    return output_path
