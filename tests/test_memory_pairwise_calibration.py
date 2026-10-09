from memory.memory_calibration_dataset import (
    get_memory_calibration_cases,
)
from memory.memory_pairwise_calibration import (
    run_memory_pairwise_calibration,
)


def _create_fake_pairwise_llm(
    cases,
    effect_overrides=None,
):
    effect_overrides = effect_overrides or {}

    effect_by_answer = {
        case["benchmark_answers"]["with_memory"]: effect_overrides.get(
            case["case_id"],
            case["expected_effect"],
        )
        for case in cases
    }

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        for (
            answer,
            effect,
        ) in effect_by_answer.items():
            if answer in user_message:
                return {
                    "status": "success",
                    "content": (
                        f'{{"effect": "{effect}", "reason": "测试 Pairwise Judge。"}}'
                    ),
                }

        raise AssertionError("Unknown benchmark answer")

    return fake_llm_call


def test_pairwise_calibration_should_evaluate_all_builtin_cases():
    cases = get_memory_calibration_cases()

    report = run_memory_pairwise_calibration(
        llm_call=(_create_fake_pairwise_llm(cases)),
        cases=cases,
    )

    assert len(report["results"]) == 12

    assert report["summary"] == {
        "total_cases": 12,
        "correct_cases": 12,
        "error_cases": 0,
        "accuracy": 1.0,
    }


def test_pairwise_calibration_should_report_category_accuracy():
    cases = get_memory_calibration_cases()

    report = run_memory_pairwise_calibration(
        llm_call=(_create_fake_pairwise_llm(cases)),
        cases=cases,
    )

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
        assert category_summary[category] == {
            "total_cases": 3,
            "correct_cases": 3,
            "error_cases": 0,
            "accuracy": 1.0,
        }


def test_pairwise_calibration_should_expose_gold_errors():
    cases = get_memory_calibration_cases()

    report = run_memory_pairwise_calibration(
        llm_call=(
            _create_fake_pairwise_llm(
                cases,
                effect_overrides={
                    ("ambiguous-management-database-design"): "negative",
                },
            )
        ),
        cases=cases,
    )

    assert report["summary"]["correct_cases"] == 11

    assert report["summary"]["error_cases"] == 1

    assert report["summary"]["accuracy"] == 11 / 12

    assert len(report["errors"]) == 1

    error = report["errors"][0]

    assert error["case_id"] == ("ambiguous-management-database-design")

    assert error["expected_effect"] == "neutral"

    assert error["pairwise_actual_effect"] == "negative"


def test_pairwise_calibration_should_handle_empty_dataset():
    report = run_memory_pairwise_calibration(
        llm_call=None,
        cases=[],
    )

    assert report["summary"] == {
        "total_cases": 0,
        "correct_cases": 0,
        "error_cases": 0,
        "accuracy": 0.0,
    }

    assert report["results"] == []

    assert report["errors"] == []
