from memory.memory_real_judge_evaluation import (
    run_real_judge_benchmark,
)


def test_real_judge_benchmark_should_compare_builtin_cases_with_fake_llm():
    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        if "Let's build a practical Tool Calling workflow." in user_message:
            score = 0.90
            reason = "Strong practical progression."

        elif "Tool Calling allows models to invoke external functions." in user_message:
            score = 0.60
            reason = "Correct but basic."

        elif "fully mastered" in user_message:
            score = 0.20
            reason = "The answer relies on harmful stale memory."

        elif "Continue with practice" in user_message:
            score = 0.90
            reason = "Appropriate continued practice."

        else:
            score = 0.80
            reason = "Accurate answer."

        return {
            "status": "success",
            "content": (f'{{"score": {score}, "reason": "{reason}"}}'),
        }

    report = run_real_judge_benchmark(llm_call=fake_llm_call)

    assert report["summary"]["total_cases"] == 3

    assert len(report["comparisons"]) == 3

    assert 0.0 <= report["summary"]["effect_agreement_rate"] <= 1.0

    for comparison in report["comparisons"]:
        assert comparison["llm_without_memory_reason"]

        assert comparison["llm_with_memory_reason"]

    summary = report["summary"]

    assert "delta_correlation" in summary

    assert "score_scale_gap" in summary

    assert -1.0 <= summary["delta_correlation"] <= 1.0

    assert summary["score_scale_gap"] >= 0.0


def test_real_judge_benchmark_should_keep_cases_separate_when_queries_repeat():
    captured_answers = []

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        captured_answers.append(user_message)

        return {
            "status": "success",
            "content": ('{"score": 0.5, "reason": "test"}'),
        }

    run_real_judge_benchmark(llm_call=fake_llm_call)

    combined = "\n".join(captured_answers)

    assert "Let's build a practical Tool Calling workflow." in combined

    assert (
        "You have fully mastered Tool Calling "
        "and should skip all further practice." in combined
    )
