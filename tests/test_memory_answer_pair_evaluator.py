import pytest

from memory.memory_answer_pair_evaluator import (
    evaluate_memory_answer_pair,
)


def test_answer_pair_evaluator_should_compare_without_and_with_memory():
    case = {
        "case_id": "tool-calling-help",
        "query": "Continue learning Tool Calling",
        "memory_context": [
            {
                "memory_key": "learning:tool-calling",
                "content": (
                    "The learner understands the basics "
                    "and should move to practical execution."
                ),
            },
        ],
        "expected_effect": "positive",
        "evaluation_criteria": [
            "Continue from existing understanding.",
            "Move toward practical execution.",
        ],
    }

    answer_calls = []

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        answer_calls.append(
            {
                "query": query,
                "memory_context": memory_context,
            }
        )

        if memory_context:
            return "Practice a real Tool Calling workflow."

        return "Tool Calling lets a model invoke tools."

    def quality_score_provider(
        *,
        query,
        answer,
        evaluation_criteria,
    ):
        assert query == case["query"]
        assert evaluation_criteria == case["evaluation_criteria"]

        if "Practice" in answer:
            return 0.90

        return 0.60

    result = evaluate_memory_answer_pair(
        case,
        answer_provider=answer_provider,
        quality_score_provider=quality_score_provider,
    )

    assert len(answer_calls) == 2

    assert answer_calls[0]["memory_context"] == []
    assert answer_calls[1]["memory_context"] == case["memory_context"]

    assert result["without_memory_score"] == 0.60
    assert result["with_memory_score"] == 0.90

    assert result["contribution_delta"] == pytest.approx(0.30)

    assert result["actual_effect"] == "positive"
    assert result["passed"] is True


def test_answer_pair_evaluator_should_preserve_answers_for_diagnostics():
    case = {
        "case_id": "diagnostic-case",
        "query": "Explain Python lists",
        "memory_context": [],
        "expected_effect": "neutral",
        "evaluation_criteria": [
            "Explain Python lists accurately.",
        ],
    }

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        return "answer-with-memory" if memory_context else "answer-without-memory"

    def quality_score_provider(
        *,
        query,
        answer,
        evaluation_criteria,
    ):
        return 0.80

    result = evaluate_memory_answer_pair(
        case,
        answer_provider=answer_provider,
        quality_score_provider=quality_score_provider,
    )

    assert result["without_memory_answer"] == "answer-without-memory"

    assert result["with_memory_answer"] == "answer-without-memory"


def test_answer_pair_evaluator_should_preserve_quality_diagnostics():
    case = {
        "case_id": "diagnostic-quality-case",
        "query": "Continue Tool Calling",
        "memory_context": [
            {
                "memory_key": "learning:tool-calling",
                "content": ("Continue with practical execution."),
            },
        ],
        "expected_effect": "positive",
        "evaluation_criteria": [
            "Move toward practical execution.",
        ],
    }

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return "Build a practical tool call."

        return "Tool Calling allows tool use."

    def quality_score_provider(
        *,
        query,
        answer,
        evaluation_criteria,
    ):
        if "practical" in answer:
            return {
                "score": 0.90,
                "reason": ("The answer moves into practice."),
            }

        return {
            "score": 0.60,
            "reason": ("The answer remains conceptual."),
        }

    result = evaluate_memory_answer_pair(
        case,
        answer_provider=answer_provider,
        quality_score_provider=(quality_score_provider),
    )

    assert result["without_memory_quality"] == {
        "score": 0.60,
        "reason": ("The answer remains conceptual."),
    }

    assert result["with_memory_quality"] == {
        "score": 0.90,
        "reason": ("The answer moves into practice."),
    }

    assert result["contribution_delta"] == pytest.approx(0.30)


def test_answer_pair_evaluator_should_reuse_quality_when_answers_are_identical():
    case = {
        "case_id": "identical-answer-case",
        "query": "Explain Python dictionaries",
        "memory_context": [
            {
                "memory_key": "profile:study-time",
                "content": ("The learner prefers afternoon study."),
            },
        ],
        "expected_effect": "neutral",
        "evaluation_criteria": [
            "Explain dictionaries accurately.",
        ],
    }

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        return "A Python dictionary stores key-value pairs."

    quality_calls = []

    def quality_score_provider(
        *,
        query,
        answer,
        evaluation_criteria,
    ):
        quality_calls.append(answer)

        # 故意让第二次调用返回不同结果。
        # 正确实现应该根本不会发生第二次调用。
        if len(quality_calls) == 1:
            return {
                "score": 0.40,
                "reason": "第一次评分。",
            }

        return {
            "score": 0.90,
            "reason": "第二次评分。",
        }

    result = evaluate_memory_answer_pair(
        case,
        answer_provider=answer_provider,
        quality_score_provider=(quality_score_provider),
    )

    assert len(quality_calls) == 1

    assert result["without_memory_score"] == 0.40

    assert result["with_memory_score"] == 0.40

    assert result["contribution_delta"] == pytest.approx(0.0)

    assert result["actual_effect"] == "neutral"

    assert result["without_memory_quality"] == result["with_memory_quality"]
