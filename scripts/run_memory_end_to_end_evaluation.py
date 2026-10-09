from memory.memory_calibration_dataset import (
    get_memory_calibration_cases,
)
from memory.memory_end_to_end_runner import (
    run_memory_end_to_end_evaluation,
)


_CASE_IDS = {
    "helpful-tool-calling-practice",
    "neutral-study-time-dictionary",
    "harmful-false-python-mastery",
}


def _select_cases():
    return [
        case
        for case in (get_memory_calibration_cases())
        if case["case_id"] in _CASE_IDS
    ]


def format_end_to_end_report(
    report,
):
    summary = report["summary"]

    lines = [
        "=" * 64,
        "Real Memory End-to-End Evaluation v1",
        "=" * 64,
        "",
        (f"案例数: {summary['total_cases']}"),
        (f"正确: {summary['correct_cases']}"),
        (f"误判: {summary['error_cases']}"),
        (f"Gold 准确率: {summary['accuracy']:.1%}"),
        "",
    ]

    for result in report["results"]:
        lines.extend(
            [
                "-" * 64,
                (f"案例: {result['case_id']}"),
                (f"类别: {result['category']}"),
                (f"Gold: {result['expected_effect']}"),
                (f"E2E Effect: {result['actual_effect']}"),
                ("是否正确: " + ("是" if result["is_correct"] else "否")),
                "",
                "无 Memory 回答:",
                result["without_memory_answer"],
                "",
                "有 Memory 回答:",
                result["with_memory_answer"],
                "",
                "Pairwise 判断理由:",
                result["pairwise_reason"],
                "",
            ]
        )

    return "\n".join(lines)


def main():
    report = run_memory_end_to_end_evaluation(_select_cases())

    print(format_end_to_end_report(report))


if __name__ == "__main__":
    main()
