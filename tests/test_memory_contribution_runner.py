import pytest

from memory.memory_contribution_dataset import (
    get_memory_contribution_evaluation_cases,
)
from memory.memory_contribution_runner import (
    run_memory_contribution_answer_evaluation,
    run_memory_contribution_evaluation,
    run_memory_contribution_rule_evaluation,
    run_memory_contribution_llm_evaluation,
    run_memory_contribution_pairwise_evaluation,
)


def test_memory_contribution_runner_should_evaluate_dataset_and_report_summary():
    cases = get_memory_contribution_evaluation_cases()

    scores = {
        "relevant-learning-memory-should-help": {
            "without_memory": 0.50,
            "with_memory": 0.80,
        },
        "irrelevant-profile-memory-should-be-neutral": {
            "without_memory": 0.70,
            "with_memory": 0.72,
        },
        "contradictory-learning-memory-should-hurt": {
            "without_memory": 0.80,
            "with_memory": 0.55,
        },
    }

    def score_provider(
        case,
        use_memory,
    ):
        score_key = "with_memory" if use_memory else "without_memory"

        return scores[case["case_id"]][score_key]

    report = run_memory_contribution_evaluation(
        cases,
        score_provider=score_provider,
    )

    assert len(report["results"]) == 3

    assert report["summary"]["total_cases"] == 3

    assert report["summary"]["passed_cases"] == 3

    assert report["summary"]["failed_cases"] == 0

    assert report["summary"]["accuracy"] == pytest.approx(1.0)


def test_memory_contribution_runner_should_preserve_case_level_results():
    cases = [
        {
            "case_id": "positive-case",
            "query": "Continue Tool Calling",
            "memory_context": [
                {
                    "memory_key": "learning:tool-calling",
                    "content": "Continue practical exercises.",
                },
            ],
            "expected_effect": "positive",
        },
    ]

    def score_provider(
        case,
        use_memory,
    ):
        if use_memory:
            return 0.90

        return 0.60

    report = run_memory_contribution_evaluation(
        cases,
        score_provider=score_provider,
    )

    result = report["results"][0]

    assert result["case_id"] == "positive-case"
    assert result["without_memory_score"] == 0.60
    assert result["with_memory_score"] == 0.90
    assert result["contribution_delta"] == pytest.approx(0.30)
    assert result["actual_effect"] == "positive"
    assert result["expected_effect"] == "positive"
    assert result["passed"] is True


def test_answer_evaluation_runner_should_evaluate_real_answer_pairs():
    cases = [
        {
            "case_id": "positive-case",
            "query": "Continue Tool Calling",
            "memory_context": [
                {
                    "memory_key": "learning:tool-calling",
                    "content": "Move to practical execution.",
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                "Move toward practical execution.",
            ],
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return "Let's build a practical tool call."

        return "Tool Calling allows tool use."

    def quality_score_provider(
        *,
        query,
        answer,
        evaluation_criteria,
    ):
        if "practical" in answer:
            return 0.90

        return 0.60

    report = run_memory_contribution_answer_evaluation(
        cases,
        answer_provider=answer_provider,
        quality_score_provider=(quality_score_provider),
    )

    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["passed_cases"] == 1
    assert report["summary"]["accuracy"] == 1.0

    result = report["results"][0]

    assert result["actual_effect"] == "positive"
    assert result["passed"] is True


def test_rule_evaluation_runner_should_classify_positive_neutral_and_negative():
    cases = [
        {
            "case_id": "positive-case",
            "query": "positive query",
            "memory_context": [
                {
                    "memory_key": "positive-memory",
                    "content": "useful memory",
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                "The answer should become practical.",
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
            "query": "neutral query",
            "memory_context": [
                {
                    "memory_key": "neutral-memory",
                    "content": "irrelevant memory",
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                "The answer should remain accurate.",
            ],
            "rule_scoring": {
                "required_phrases": [
                    "accurate",
                ],
                "forbidden_phrases": [],
            },
        },
        {
            "case_id": "negative-case",
            "query": "negative query",
            "memory_context": [
                {
                    "memory_key": "negative-memory",
                    "content": "misleading memory",
                },
            ],
            "expected_effect": "negative",
            "evaluation_criteria": [
                "The answer should recommend practice.",
            ],
            "rule_scoring": {
                "required_phrases": [
                    "practice",
                ],
                "forbidden_phrases": [
                    "skip practice",
                ],
            },
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if query == "positive query":
            if memory_context:
                return "Use a practical exercise."

            return "General explanation."

        if query == "neutral query":
            return "This is an accurate answer."

        if memory_context:
            return "You should skip practice."

        return "Continue practice."

    report = run_memory_contribution_rule_evaluation(
        cases,
        answer_provider=answer_provider,
    )

    assert report["summary"]["total_cases"] == 3

    assert report["summary"]["passed_cases"] == 3

    assert report["summary"]["failed_cases"] == 0

    assert report["summary"]["accuracy"] == pytest.approx(1.0)


def test_llm_evaluation_runner_should_use_semantic_judge_scores():
    cases = [
        {
            "case_id": "llm-positive-case",
            "query": "Continue Tool Calling",
            "memory_context": [
                {
                    "memory_key": ("learning:tool-calling"),
                    "content": ("Move to practical execution."),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                ("The answer should move toward practical execution."),
            ],
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return "Let's build a real tool call."

        return "Tool Calling allows tool use."

    judge_calls = []

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        judge_calls.append(user_message)

        if "real tool call" in user_message:
            score = 0.90
        else:
            score = 0.60

        return {
            "status": "success",
            "content": (f'{{"score": {score}, "reason": "test judge"}}'),
        }

    report = run_memory_contribution_llm_evaluation(
        cases,
        answer_provider=answer_provider,
        llm_call=fake_llm_call,
    )

    assert len(judge_calls) == 2

    assert report["summary"]["total_cases"] == 1

    assert report["summary"]["passed_cases"] == 1

    assert report["summary"]["accuracy"] == 1.0

    assert report["results"][0]["actual_effect"] == "positive"

    result = report["results"][0]

    assert result["without_memory_quality"]["reason"] == "test judge"

    assert result["with_memory_quality"]["reason"] == "test judge"


def test_run_pairwise_evaluation_should_classify_memory_effect():
    cases = [
        {
            "case_id": "pairwise-positive",
            "query": "Continue learning Tool Calling",
            "memory_context": [
                {
                    "memory_key": "learning:tool-calling",
                    "content": (
                        "The learner understands the basics and needs practice."
                    ),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                ("Move from concepts toward practical Tool Calling."),
            ],
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return "Let's build a practical Tool Calling workflow."

        return "Tool Calling lets models invoke external functions."

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "success",
            "content": (
                '{"effect": "positive", '
                '"reason": '
                '"有 Memory 的回答从概念介绍推进到了实践。"}'
            ),
        }

    report = run_memory_contribution_pairwise_evaluation(
        cases,
        answer_provider=answer_provider,
        llm_call=fake_llm_call,
    )

    assert report["summary"] == {
        "total_cases": 1,
        "correct_cases": 1,
        "error_cases": 0,
        "accuracy": 1.0,
    }

    result = report["results"][0]

    assert result["case_id"] == ("pairwise-positive")

    assert result["expected_effect"] == "positive"

    assert result["actual_effect"] == "positive"

    assert result["is_correct"] is True

    assert result["pairwise_reason"] == ("有 Memory 的回答从概念介绍推进到了实践。")

    assert result["without_memory_answer"] == (
        "Tool Calling lets models invoke external functions."
    )

    assert result["with_memory_answer"] == (
        "Let's build a practical Tool Calling workflow."
    )


def test_run_pairwise_evaluation_should_report_accuracy():
    cases = [
        {
            "case_id": "case-positive",
            "query": "Query A",
            "memory_context": [
                {"content": "Memory A"},
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                "Criterion A",
            ],
        },
        {
            "case_id": "case-neutral",
            "query": "Query B",
            "memory_context": [
                {"content": "Memory B"},
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                "Criterion B",
            ],
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        suffix = "with memory" if memory_context else "without memory"

        return f"{query} {suffix}"

    effects = iter(
        [
            "positive",
            "negative",
        ]
    )

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        effect = next(effects)

        return {
            "status": "success",
            "content": (f'{{"effect": "{effect}", "reason": "测试判断。"}}'),
        }

    report = run_memory_contribution_pairwise_evaluation(
        cases,
        answer_provider=answer_provider,
        llm_call=fake_llm_call,
    )

    assert report["summary"] == {
        "total_cases": 2,
        "correct_cases": 1,
        "error_cases": 1,
        "accuracy": 0.5,
    }

    assert len(report["errors"]) == 1

    assert report["errors"][0]["case_id"] == "case-neutral"


def test_run_pairwise_evaluation_should_forward_reference_context():
    cases = [
        {
            "case_id": "reference-case",
            "query": "Continue learning Python",
            "memory_context": [
                {
                    "memory_key": ("learning:python-mastery"),
                    "content": ("The learner has fully mastered Python."),
                },
            ],
            "expected_effect": "negative",
            "evaluation_criteria": [
                "Preserve useful practice.",
            ],
            "reference_context": [
                ("The learner has not fully mastered Python."),
            ],
        },
    ]

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return "Skip practice."

        return "Continue practice."

    captured = {}

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        captured["user_message"] = user_message

        return {
            "status": "success",
            "content": ('{"effect": "negative", "reason": "错误记忆造成伤害。"}'),
        }

    run_memory_contribution_pairwise_evaluation(
        cases,
        answer_provider=answer_provider,
        llm_call=fake_llm_call,
    )

    assert "The learner has not fully mastered Python" in captured["user_message"]
