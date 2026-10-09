from memory.memory_defense_dataset import (
    get_memory_defense_cases,
)
from memory.memory_defense_runner import (
    run_memory_defense_evaluation,
)


def format_memory_defense_report(
    report,
):
    summary = report["summary"]

    lines = [
        "=" * 64,
        "Memory Defense Evaluation v1",
        "=" * 64,
        "",
        (f"案例数: {summary['total_cases']}"),
        (f"正确: {summary['correct_cases']}"),
        (f"错误: {summary['error_cases']}"),
        (f"Defense 准确率: {summary['accuracy']:.1%}"),
        "",
    ]

    for result in report["results"]:
        lines.extend(
            [
                "-" * 64,
                (f"案例: {result['case_id']}"),
                (f"目标 Memory: {result['target_memory_key']}"),
                (f"Gold Defense: {result['expected_defense']}"),
                (f"Actual Defense: {result['actual_defense']}"),
                ("是否正确: " + ("是" if result["is_correct"] else "否")),
                ("Blocked: " + str(result["blocked_memory_keys"])),
                "",
            ]
        )

    return "\n".join(lines)


def main():
    report = run_memory_defense_evaluation(get_memory_defense_cases())

    print(format_memory_defense_report(report))


if __name__ == "__main__":
    main()
