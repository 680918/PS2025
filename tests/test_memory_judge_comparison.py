import pytest

from memory.memory_judge_comparison import (
    compare_memory_contribution_judges,
)


def test_judge_comparison_should_report_effect_agreement():
    cases = [
        {
            "case_id": "positive-case",
            "query": "Continue Tool Calling",
            "memory_context": [
                {
                    "memory_key": "learning:tool-calling",
                    "content": ("Move toward practical execution."),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                ("The answer should move toward practical execution."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "practical",
                ],
                "forbidden_phrases": [],
            },
        },
        {
            "case_id": "neutral-case",
            "query": "Explain Python lists",
            "memory_context": [
                {
                    "memory_key": "profile:study-time",
                    "content": ("The learner studies in the afternoon."),
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                "Explain Python lists accurately.",
            ],
            "rule_scoring": {
                "required_phrases": [
                    "accurate",
                ],
                "forbidden_phrases": [],
            },
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if query == "Continue Tool Calling":
            if memory_context:
                return "Let's build a practical Tool Calling workflow."

            return "Tool Calling allows tool use."

        return "Python lists provide an accurate ordered collection."

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        if "practical Tool Calling workflow" in user_message:
            score = 0.90
            reason = "The answer moves into practice."

        elif "Tool Calling allows tool use" in user_message:
            score = 0.60
            reason = "The answer remains conceptual."

        else:
            score = 0.80
            reason = "The answer is accurate."

        return {
            "status": "success",
            "content": (f'{{"score": {score}, "reason": "{reason}"}}'),
        }

    report = compare_memory_contribution_judges(
        cases,
        answer_provider=answer_provider,
        llm_call=fake_llm_call,
    )

    summary = report["summary"]

    assert summary["total_cases"] == 2

    assert summary["effect_agreements"] == 2

    assert summary["effect_disagreements"] == 0

    assert summary["effect_agreement_rate"] == pytest.approx(1.0)

    assert -1.0 <= summary["delta_correlation"] <= 1.0

    assert summary["score_scale_gap"] >= 0.0

    positive = report["comparisons"][0]

    assert positive["rule_actual_effect"] == "positive"

    assert positive["llm_actual_effect"] == "positive"

    assert positive["effect_agreement"] is True


def test_judge_comparison_should_expose_semantic_disagreement():
    cases = [
        {
            "case_id": "disagreement-case",
            "query": "Continue Tool Calling",
            "memory_context": [
                {
                    "memory_key": "learning:tool-calling",
                    "content": ("Move toward practical execution."),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                ("The answer should meaningfully improve practical guidance."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "practical",
                ],
                "forbidden_phrases": [],
            },
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return "Here is a practical explanation."

        return "Here is a general explanation."

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        if "practical explanation" in user_message:
            score = 0.82
            reason = "The wording changes, but the practical improvement is small."
        else:
            score = 0.80
            reason = "The baseline answer is already adequate."

        return {
            "status": "success",
            "content": (f'{{"score": {score}, "reason": "{reason}"}}'),
        }

    report = compare_memory_contribution_judges(
        cases,
        answer_provider=answer_provider,
        llm_call=fake_llm_call,
    )

    comparison = report["comparisons"][0]

    assert comparison["rule_actual_effect"] == "positive"

    assert comparison["llm_actual_effect"] == "neutral"

    assert comparison["effect_agreement"] is False

    assert report["summary"]["effect_disagreements"] == 1

    assert comparison["llm_with_memory_reason"] == (
        "The wording changes, but the practical improvement is small."
    )


def test_judge_comparison_should_handle_empty_dataset():
    def answer_provider(
        *,
        query,
        memory_context,
    ):
        raise AssertionError("answer provider should not be called")

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        raise AssertionError("LLM should not be called")

    report = compare_memory_contribution_judges(
        [],
        answer_provider=answer_provider,
        llm_call=fake_llm_call,
    )

    assert report["comparisons"] == []

    assert report["summary"] == {
        "total_cases": 0,
        "effect_agreements": 0,
        "effect_disagreements": 0,
        "effect_agreement_rate": 0.0,
        "mean_contribution_delta_gap": 0.0,
        "delta_correlation": 0.0,
        "score_scale_gap": 0.0,
        "score_bias": 0.0,
    }
