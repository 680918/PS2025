import pytest

from memory.memory_calibration_dataset import (
    get_memory_calibration_cases,
)
from memory.memory_calibration_runner import (
    run_memory_calibration,
)


def _create_fake_llm_call(
    cases,
):
    answer_scores = {}

    for case in cases:
        answers = case["benchmark_answers"]

        expected_effect = case["expected_effect"]

        if expected_effect == "positive":
            without_score = 0.40
            with_score = 0.80

        elif expected_effect == "negative":
            without_score = 0.80
            with_score = 0.30

        else:
            without_score = 0.60
            with_score = 0.60

        answer_scores[answers["without_memory"]] = without_score

        answer_scores[answers["with_memory"]] = with_score

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        for (
            answer,
            score,
        ) in answer_scores.items():
            if answer in user_message:
                return {
                    "status": "success",
                    "content": (f'{{"score": {score}, "reason": "测试 Judge 结果。"}}'),
                }

        raise AssertionError("Unknown benchmark answer")

    return fake_llm_call


def test_memory_calibration_runner_should_evaluate_all_builtin_cases():
    cases = get_memory_calibration_cases()

    report = run_memory_calibration(llm_call=_create_fake_llm_call(cases))

    assert len(report["comparisons"]) == 12

    assert report["summary"]["total_cases"] == 12

    assert report["summary"]["rule_expected_accuracy"] == pytest.approx(1.0)

    assert report["summary"]["llm_expected_accuracy"] == pytest.approx(1.0)

    assert report["summary"]["effect_agreement_rate"] == pytest.approx(1.0)


def test_memory_calibration_runner_should_report_category_metrics():
    cases = get_memory_calibration_cases()

    report = run_memory_calibration(llm_call=_create_fake_llm_call(cases))

    category_summary = report["category_summary"]

    assert set(category_summary) == {
        "helpful",
        "neutral",
        "harmful",
        "ambiguous",
    }

    for category in (
        "helpful",
        "neutral",
        "harmful",
        "ambiguous",
    ):
        metrics = category_summary[category]

        assert metrics["total_cases"] == 3

        assert 0.0 <= metrics["rule_expected_accuracy"] <= 1.0

        assert 0.0 <= metrics["llm_expected_accuracy"] <= 1.0

        assert 0.0 <= metrics["effect_agreement_rate"] <= 1.0


def test_memory_calibration_runner_should_preserve_case_metadata():
    cases = get_memory_calibration_cases()

    report = run_memory_calibration(llm_call=_create_fake_llm_call(cases))

    comparison = report["comparisons"][0]

    assert comparison["category"] == "helpful"

    assert comparison["domain"]

    assert comparison["description"]
