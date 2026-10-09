from llm_client import call_llm

from memory.memory_pairwise_stability import (
    run_memory_pairwise_stability,
)


def format_pairwise_stability_report(
    report,
):
    lines = [
        "=" * 64,
        "Pairwise Memory Judge Stability v1",
        "=" * 64,
        "",
        (f"运行次数: {report['runs']}"),
        (f"案例数量: {report['total_cases']}"),
        "",
        "每轮 Gold 准确率:",
    ]

    for index, accuracy in enumerate(
        report["run_accuracies"],
        start=1,
    ):
        lines.append(f"  Run {index}: {accuracy:.1%}")

    lines.extend(
        [
            "",
            (f"平均准确率: {report['mean_accuracy']:.1%}"),
            (f"最低准确率: {report['min_accuracy']:.1%}"),
            (f"最高准确率: {report['max_accuracy']:.1%}"),
            (f"稳定正确案例: {report['stable_correct_cases']}/{report['total_cases']}"),
            (f"不稳定案例数量: {report['unstable_case_count']}"),
            (
                "共识正确案例: "
                f"{report['consensus_correct_cases']}"
                f"/{report['total_cases']}"
            ),
            (f"共识 Gold 准确率: {report['consensus_accuracy']:.1%}"),
            "",
            "-" * 64,
            "不稳定案例:",
            "",
        ]
    )

    if not report["unstable_cases"]:
        lines.append("无不稳定案例。")

    for case in report["unstable_cases"]:
        lines.extend(
            [
                (f"案例: {case['case_id']}"),
                (f"  类别: {case['category']}"),
                (f"  Gold: {case['expected_effect']}"),
                (f"  多轮判断: {case['observed_effects']}"),
                (f"  Gold 准确率: {case['gold_accuracy']:.1%}"),
                ("  判断是否一致: " + ("是" if case["effect_consistent"] else "否")),
                (f"  共识判断: {case['consensus_effect']}"),
                (f"  共识置信度: {case['consensus_rate']:.1%}"),
                (
                    "  共识是否命中 Gold: "
                    + ("是" if case["consensus_correct"] else "否")
                ),
                "",
            ]
        )

    return "\n".join(lines)


def main():
    report = run_memory_pairwise_stability(
        llm_call=call_llm,
        runs=3,
    )

    print(format_pairwise_stability_report(report))


if __name__ == "__main__":
    main()
