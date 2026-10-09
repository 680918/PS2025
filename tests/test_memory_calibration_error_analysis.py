from memory.memory_calibration_error_analysis import (
    analyze_memory_calibration_errors,
)


def test_calibration_error_analysis_should_find_gold_errors():
    report = {
        "comparisons": [
            {
                "case_id": "correct-case",
                "category": "helpful",
                "expected_effect": "positive",
                "rule_actual_effect": "positive",
                "llm_actual_effect": "positive",
                "effect_agreement": True,
            },
            {
                "case_id": "llm-error-case",
                "category": "ambiguous",
                "expected_effect": "neutral",
                "rule_actual_effect": "neutral",
                "llm_actual_effect": "positive",
                "effect_agreement": False,
            },
            {
                "case_id": "both-error-case",
                "category": "ambiguous",
                "expected_effect": "neutral",
                "rule_actual_effect": "positive",
                "llm_actual_effect": "positive",
                "effect_agreement": True,
            },
        ],
    }

    analysis = analyze_memory_calibration_errors(report)

    assert analysis["total_cases"] == 3

    assert analysis["llm_gold_error_count"] == 2

    assert analysis["rule_gold_error_count"] == 1

    assert analysis["judge_disagreement_count"] == 1

    assert len(analysis["llm_gold_errors"]) == 2

    assert len(analysis["rule_gold_errors"]) == 1


def test_calibration_error_analysis_should_group_llm_errors_by_category():
    report = {
        "comparisons": [
            {
                "case_id": "ambiguous-1",
                "category": "ambiguous",
                "expected_effect": "neutral",
                "rule_actual_effect": "neutral",
                "llm_actual_effect": "positive",
                "effect_agreement": False,
            },
            {
                "case_id": "ambiguous-2",
                "category": "ambiguous",
                "expected_effect": "neutral",
                "rule_actual_effect": "neutral",
                "llm_actual_effect": "negative",
                "effect_agreement": False,
            },
            {
                "case_id": "neutral-1",
                "category": "neutral",
                "expected_effect": "neutral",
                "rule_actual_effect": "neutral",
                "llm_actual_effect": "neutral",
                "effect_agreement": True,
            },
        ],
    }

    analysis = analyze_memory_calibration_errors(report)

    assert analysis["llm_errors_by_category"] == {
        "ambiguous": 2,
    }


def test_calibration_error_analysis_should_handle_no_errors():
    report = {
        "comparisons": [],
    }

    analysis = analyze_memory_calibration_errors(report)

    assert analysis == {
        "total_cases": 0,
        "llm_gold_error_count": 0,
        "rule_gold_error_count": 0,
        "judge_disagreement_count": 0,
        "llm_gold_errors": [],
        "rule_gold_errors": [],
        "judge_disagreements": [],
        "llm_errors_by_category": {},
    }
