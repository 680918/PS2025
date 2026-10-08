from llm_client import call_llm

from memory.memory_real_judge_evaluation import (
    run_real_judge_benchmark,
)


_EFFECT_LABELS = {
    "positive": "正向提升",
    "neutral": "基本无影响",
    "negative": "负向影响",
}


_CASE_LABELS = {
    ("relevant-learning-memory-should-help"): ("相关学习记忆应提升回答质量"),
    ("irrelevant-profile-memory-should-be-neutral"): ("无关用户画像记忆应基本无影响"),
    ("contradictory-learning-memory-should-hurt"): ("矛盾或过期学习记忆应降低回答质量"),
}


def _effect_label(
    effect,
):
    return _EFFECT_LABELS.get(
        effect,
        effect,
    )


def _case_label(
    case_id,
):
    return _CASE_LABELS.get(
        case_id,
        case_id,
    )


def format_memory_judge_report(
    report,
):
    summary = report["summary"]

    lines = [
        "=" * 60,
        "Memory Judge 校准评估报告",
        "=" * 60,
        "",
        (f"案例数量: {summary['total_cases']}"),
        (f"方向一致: {summary['effect_agreements']}"),
        (f"方向分歧: {summary['effect_disagreements']}"),
        (f"方向一致率: {summary['effect_agreement_rate']:.1%}"),
        "",
        "Judge 校准指标:",
        (f"  贡献变化相关性: {summary['delta_correlation']:.3f}"),
        (f"  平均贡献差异: {summary['mean_contribution_delta_gap']:.3f}"),
        (f"  评分尺度差: {summary['score_scale_gap']:.3f}"),
        (f"  评分偏差（LLM - Rule）: {summary['score_bias']:+.3f}"),
        "",
    ]

    for comparison in report["comparisons"]:
        case_id = comparison["case_id"]

        lines.extend(
            [
                "-" * 60,
                (f"案例: {_case_label(case_id)}"),
                (f"案例 ID: {case_id}"),
                "",
                (f"预期 Memory 效果: {_effect_label(comparison['expected_effect'])}"),
                "",
                "Rule Judge:",
                (f"  判断: {_effect_label(comparison['rule_actual_effect'])}"),
                (f"  无 Memory 分数: {comparison['rule_without_memory_score']:.3f}"),
                (f"  有 Memory 分数: {comparison['rule_with_memory_score']:.3f}"),
                (f"  贡献变化: {comparison['rule_contribution_delta']:+.3f}"),
                "",
                "LLM Judge:",
                (f"  判断: {_effect_label(comparison['llm_actual_effect'])}"),
                (f"  无 Memory 分数: {comparison['llm_without_memory_score']:.3f}"),
                (f"  有 Memory 分数: {comparison['llm_with_memory_score']:.3f}"),
                (f"  贡献变化: {comparison['llm_contribution_delta']:+.3f}"),
                "",
                ("方向是否一致: " + ("是" if comparison["effect_agreement"] else "否")),
                "",
                "LLM 判断理由:",
                "  无 Memory:",
                ("    " + comparison["llm_without_memory_reason"]),
                "",
                "  有 Memory:",
                ("    " + comparison["llm_with_memory_reason"]),
                "",
            ]
        )

    return "\n".join(lines)


def main():
    report = run_real_judge_benchmark(llm_call=call_llm)

    print(format_memory_judge_report(report))


if __name__ == "__main__":
    main()
