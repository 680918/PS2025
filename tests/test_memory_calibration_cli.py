from scripts.run_memory_calibration import (
    format_memory_calibration_report,
)


def test_memory_calibration_report_should_render_chinese_summary():
    report = {
        "summary": {
            "total_cases": 12,
            "effect_agreements": 10,
            "effect_disagreements": 2,
            "effect_agreement_rate": 10 / 12,
            "mean_contribution_delta_gap": 0.15,
            "delta_correlation": 0.88,
            "score_scale_gap": 0.20,
            "score_bias": -0.10,
            "rule_expected_accuracy": 10 / 12,
            "llm_expected_accuracy": 11 / 12,
        },
        "category_summary": {
            "helpful": {
                "total_cases": 3,
                "effect_agreements": 3,
                "effect_disagreements": 0,
                "effect_agreement_rate": 1.0,
                "mean_contribution_delta_gap": 0.10,
                "delta_correlation": 0.95,
                "score_scale_gap": 0.20,
                "score_bias": -0.10,
                "rule_expected_accuracy": 1.0,
                "llm_expected_accuracy": 1.0,
            },
            "neutral": {
                "total_cases": 3,
                "effect_agreements": 2,
                "effect_disagreements": 1,
                "effect_agreement_rate": 2 / 3,
                "mean_contribution_delta_gap": 0.15,
                "delta_correlation": 0.80,
                "score_scale_gap": 0.15,
                "score_bias": -0.05,
                "rule_expected_accuracy": 2 / 3,
                "llm_expected_accuracy": 1.0,
            },
            "harmful": {
                "total_cases": 3,
                "effect_agreements": 3,
                "effect_disagreements": 0,
                "effect_agreement_rate": 1.0,
                "mean_contribution_delta_gap": 0.10,
                "delta_correlation": 0.98,
                "score_scale_gap": 0.20,
                "score_bias": -0.12,
                "rule_expected_accuracy": 1.0,
                "llm_expected_accuracy": 1.0,
            },
            "ambiguous": {
                "total_cases": 3,
                "effect_agreements": 2,
                "effect_disagreements": 1,
                "effect_agreement_rate": 2 / 3,
                "mean_contribution_delta_gap": 0.25,
                "delta_correlation": 0.60,
                "score_scale_gap": 0.25,
                "score_bias": -0.15,
                "rule_expected_accuracy": 2 / 3,
                "llm_expected_accuracy": 2 / 3,
            },
        },
        "comparisons": [],
    }

    output = format_memory_calibration_report(report)

    assert "Memory Judge Calibration Set v1" in output
    assert "总案例数: 12" in output
    assert "Rule Gold 准确率: 83.3%" in output
    assert "LLM Gold 准确率: 91.7%" in output
    assert "Rule / LLM 方向一致率: 83.3%" in output
    assert "贡献变化相关性: 0.880" in output
    assert "评分偏差（LLM - Rule）: -0.100" in output

    assert "Helpful / 有帮助记忆" in output
    assert "Neutral / 无关记忆" in output
    assert "Harmful / 有害记忆" in output
    assert "Ambiguous / 边界记忆" in output


def test_memory_calibration_report_should_render_llm_gold_errors():
    report = {
        "summary": {
            "total_cases": 1,
            "effect_agreements": 0,
            "effect_disagreements": 1,
            "effect_agreement_rate": 0.0,
            "mean_contribution_delta_gap": 0.20,
            "delta_correlation": 0.0,
            "score_scale_gap": 0.30,
            "score_bias": -0.30,
            "rule_expected_accuracy": 1.0,
            "llm_expected_accuracy": 0.0,
        },
        "category_summary": {
            category: {
                "total_cases": (1 if category == "ambiguous" else 0),
                "effect_agreements": 0,
                "effect_disagreements": (1 if category == "ambiguous" else 0),
                "effect_agreement_rate": 0.0,
                "mean_contribution_delta_gap": 0.0,
                "delta_correlation": 0.0,
                "score_scale_gap": 0.0,
                "score_bias": 0.0,
                "rule_expected_accuracy": (1.0 if category == "ambiguous" else 0.0),
                "llm_expected_accuracy": 0.0,
            }
            for category in (
                "helpful",
                "neutral",
                "harmful",
                "ambiguous",
            )
        },
        "comparisons": [
            {
                "case_id": "ambiguous-case",
                "category": "ambiguous",
                "domain": "ai",
                "description": "Boundary case.",
                "expected_effect": "neutral",
                "rule_actual_effect": "neutral",
                "llm_actual_effect": "positive",
                "effect_agreement": False,
                "rule_contribution_delta": 0.0,
                "llm_contribution_delta": 0.20,
                "rule_without_memory_score": 0.50,
                "rule_with_memory_score": 0.50,
                "llm_without_memory_score": 0.40,
                "llm_with_memory_score": 0.60,
                "llm_without_memory_reason": ("基础回答。"),
                "llm_with_memory_reason": ("Memory 改善了回答组织方式。"),
            },
        ],
    }

    output = format_memory_calibration_report(report)

    assert "错误分析:" in output
    assert "LLM Gold 误判数量: 1" in output
    assert "案例: ambiguous-case" in output
    assert "Gold: neutral" in output
    assert "LLM: positive" in output
    assert "Memory 改善了回答组织方式。" in output
