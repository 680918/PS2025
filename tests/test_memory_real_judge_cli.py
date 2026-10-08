from scripts.run_memory_real_judge_evaluation import (
    format_memory_judge_report,
)


def test_real_judge_report_should_render_chinese_summary_and_diagnostics():
    report = {
        "summary": {
            "total_cases": 1,
            "effect_agreements": 1,
            "effect_disagreements": 0,
            "effect_agreement_rate": 1.0,
            "mean_contribution_delta_gap": 0.25,
            "delta_correlation": 0.96,
            "score_scale_gap": 0.10,
            "score_bias": -0.20,
        },
        "comparisons": [
            {
                "case_id": ("relevant-learning-memory-should-help"),
                "expected_effect": "positive",
                "rule_actual_effect": "positive",
                "llm_actual_effect": "positive",
                "effect_agreement": True,
                "rule_without_memory_score": 0.75,
                "rule_with_memory_score": 1.00,
                "llm_without_memory_score": 0.40,
                "llm_with_memory_score": 0.90,
                "rule_contribution_delta": 0.25,
                "llm_contribution_delta": 0.50,
                "llm_without_memory_reason": ("回答仍停留在基础定义。"),
                "llm_with_memory_reason": ("回答已经进入实际操作。"),
            },
        ],
    }

    output = format_memory_judge_report(report)

    assert "Memory Judge 校准评估报告" in output

    assert "方向一致率: 100.0%" in output

    assert "贡献变化相关性: 0.960" in output

    assert "评分尺度差: 0.100" in output

    assert "正向提升" in output

    assert "相关学习记忆应提升回答质量" in output

    assert "回答已经进入实际操作。" in output
    assert "评分偏差（LLM - Rule）: -0.200" in output

    assert "无 Memory 分数: 0.750" in output

    assert "有 Memory 分数: 0.900" in output
