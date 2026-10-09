from llm_client import call_llm

from memory.memory_pairwise_calibration import (
    run_memory_pairwise_calibration,
)


_CATEGORY_LABELS = {
    "helpful": "Helpful / 有帮助记忆",
    "neutral": "Neutral / 无关记忆",
    "harmful": "Harmful / 有害记忆",
    "ambiguous": "Ambiguous / 边界记忆",
}


def format_pairwise_calibration_report(
    report,
):
    summary = report["summary"]

    lines = [
        "=" * 64,
        "Pairwise Memory Judge Calibration v1",
        "=" * 64,
        "",
        (f"总案例数: {summary['total_cases']}"),
        (f"正确案例: {summary['correct_cases']}"),
        (f"误判案例: {summary['error_cases']}"),
        (f"Pairwise Gold 准确率: {summary['accuracy']:.1%}"),
        "",
        "-" * 64,
        "按类别:",
        "",
    ]

    for category in (
        "helpful",
        "neutral",
        "harmful",
        "ambiguous",
    ):
        metrics = report["category_summary"][category]

        lines.extend(
            [
                _CATEGORY_LABELS[category],
                (f"  案例数: {metrics['total_cases']}"),
                (f"  正确: {metrics['correct_cases']}"),
                (f"  准确率: {metrics['accuracy']:.1%}"),
                "",
            ]
        )

    lines.extend(
        [
            "-" * 64,
            "误判分析:",
            "",
        ]
    )

    if not report["errors"]:
        lines.append("无误判案例。")

    for error in report["errors"]:
        lines.extend(
            [
                (f"案例: {error['case_id']}"),
                (f"  类别: {error['category']}"),
                (f"  Gold: {error['expected_effect']}"),
                (f"  Pairwise: {error['pairwise_actual_effect']}"),
                "  判断理由:",
                ("    " + error["pairwise_reason"]),
                "",
            ]
        )

    return "\n".join(lines)


def main():
    report = run_memory_pairwise_calibration(llm_call=call_llm)

    print(format_pairwise_calibration_report(report))


if __name__ == "__main__":
    main()
