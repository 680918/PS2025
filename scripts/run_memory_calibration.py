from llm_client import call_llm

from memory.memory_calibration_runner import (
    run_memory_calibration,
)
from memory.memory_calibration_error_analysis import (
    analyze_memory_calibration_errors,
)

_CATEGORY_LABELS = {
    "helpful": "Helpful / 有帮助记忆",
    "neutral": "Neutral / 无关记忆",
    "harmful": "Harmful / 有害记忆",
    "ambiguous": "Ambiguous / 边界记忆",
}


def _format_category_metrics(
    category,
    metrics,
):
    label = _CATEGORY_LABELS.get(
        category,
        category,
    )

    return [
        f"{label}",
        (f"  案例数: {metrics['total_cases']}"),
        (f"  Rule Gold 准确率: {metrics['rule_expected_accuracy']:.1%}"),
        (f"  LLM Gold 准确率: {metrics['llm_expected_accuracy']:.1%}"),
        (f"  Rule / LLM 方向一致率: {metrics['effect_agreement_rate']:.1%}"),
        (f"  贡献变化相关性: {metrics['delta_correlation']:.3f}"),
        (f"  平均贡献差异: {metrics['mean_contribution_delta_gap']:.3f}"),
        (f"  评分尺度差: {metrics['score_scale_gap']:.3f}"),
        (f"  评分偏差（LLM - Rule）: {metrics['score_bias']:+.3f}"),
        "",
    ]


def format_memory_calibration_report(
    report,
):
    summary = report["summary"]

    lines = [
        "=" * 64,
        "Memory Judge Calibration Set v1",
        "=" * 64,
        "",
        f"总案例数: {summary['total_cases']}",
        "",
        "整体校准结果:",
        (f"  Rule Gold 准确率: {summary['rule_expected_accuracy']:.1%}"),
        (f"  LLM Gold 准确率: {summary['llm_expected_accuracy']:.1%}"),
        (f"  Rule / LLM 方向一致率: {summary['effect_agreement_rate']:.1%}"),
        (f"  贡献变化相关性: {summary['delta_correlation']:.3f}"),
        (f"  平均贡献差异: {summary['mean_contribution_delta_gap']:.3f}"),
        (f"  评分尺度差: {summary['score_scale_gap']:.3f}"),
        (f"  评分偏差（LLM - Rule）: {summary['score_bias']:+.3f}"),
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
            _format_category_metrics(
                category,
                metrics,
            )
        )

    analysis = analyze_memory_calibration_errors(report)

    lines.extend(
        [
            "-" * 64,
            "错误分析:",
            "",
            (f"LLM Gold 误判数量: {analysis['llm_gold_error_count']}"),
            (f"Rule Gold 误判数量: {analysis['rule_gold_error_count']}"),
            (f"Rule / LLM 分歧数量: {analysis['judge_disagreement_count']}"),
            "",
        ]
    )

    for comparison in analysis["llm_gold_errors"]:
        lines.extend(
            [
                (f"案例: {comparison['case_id']}"),
                (f"  类别: {comparison['category']}"),
                (f"  Gold: {comparison['expected_effect']}"),
                (f"  Rule: {comparison['rule_actual_effect']}"),
                (f"  LLM: {comparison['llm_actual_effect']}"),
                (f"  Rule delta: {comparison['rule_contribution_delta']:+.3f}"),
                (f"  LLM delta: {comparison['llm_contribution_delta']:+.3f}"),
                (f"  LLM 无 Memory 分数: {comparison['llm_without_memory_score']:.3f}"),
                (f"  LLM 有 Memory 分数: {comparison['llm_with_memory_score']:.3f}"),
                "  LLM 无 Memory 理由:",
                ("    " + comparison["llm_without_memory_reason"]),
                "  LLM 有 Memory 理由:",
                ("    " + comparison["llm_with_memory_reason"]),
                "",
            ]
        )

    return "\n".join(lines)


def main():
    report = run_memory_calibration(llm_call=call_llm)

    print(format_memory_calibration_report(report))


if __name__ == "__main__":
    main()
