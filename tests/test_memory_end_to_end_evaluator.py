import pytest

from memory.memory_end_to_end_evaluator import (
    evaluate_memory_end_to_end_case,
)


def test_end_to_end_evaluator_should_run_agent_without_and_with_memory():
    case = {
        "case_id": "tool-calling-practice",
        "query": "Continue learning Tool Calling",
        "memory_context": [
            {
                "memory_key": "learning:tool-calling",
                "content": (
                    "The learner understands "
                    "Tool Calling basics and "
                    "needs practical exercises."
                ),
            },
        ],
        "expected_effect": "positive",
        "evaluation_criteria": [
            ("Move from conceptual knowledge toward practical Tool Calling."),
        ],
    }

    calls = []

    def fake_agent_runner(
        *,
        query,
        memory_context,
    ):
        calls.append(
            {
                "query": query,
                "memory_context": memory_context,
            }
        )

        if memory_context:
            return "Let's build a practical Tool Calling workflow."

        return "Tool Calling allows a model to invoke external tools."

    captured = {}

    def fake_pairwise_judge(
        *,
        query,
        without_memory_answer,
        with_memory_answer,
        evaluation_criteria,
    ):
        captured["query"] = query
        captured["without_memory_answer"] = without_memory_answer
        captured["with_memory_answer"] = with_memory_answer
        captured["evaluation_criteria"] = evaluation_criteria

        return {
            "effect": "positive",
            "reason": ("有 Memory 后回答从概念解释 推进到了实际练习。"),
        }

    result = evaluate_memory_end_to_end_case(
        case,
        agent_runner=fake_agent_runner,
        pairwise_judge=(fake_pairwise_judge),
    )

    assert calls == [
        {
            "query": ("Continue learning Tool Calling"),
            "memory_context": [],
        },
        {
            "query": ("Continue learning Tool Calling"),
            "memory_context": (case["memory_context"]),
        },
    ]

    assert captured["without_memory_answer"] == (
        "Tool Calling allows a model to invoke external tools."
    )

    assert captured["with_memory_answer"] == (
        "Let's build a practical Tool Calling workflow."
    )

    assert result["actual_effect"] == "positive"

    assert result["expected_effect"] == "positive"

    assert result["is_correct"] is True


def test_end_to_end_evaluator_should_preserve_answers_and_reason():
    case = {
        "case_id": "neutral-profile-memory",
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

    def fake_agent_runner(
        *,
        query,
        memory_context,
    ):
        return "A Python dictionary stores key-value pairs."

    def fake_pairwise_judge(
        *,
        query,
        without_memory_answer,
        with_memory_answer,
        evaluation_criteria,
    ):
        return {
            "effect": "neutral",
            "reason": ("两份回答没有实质性质量差异。"),
        }

    result = evaluate_memory_end_to_end_case(
        case,
        agent_runner=fake_agent_runner,
        pairwise_judge=(fake_pairwise_judge),
    )

    assert result == {
        "case_id": ("neutral-profile-memory"),
        "expected_effect": "neutral",
        "actual_effect": "neutral",
        "is_correct": True,
        "without_memory_answer": ("A Python dictionary stores key-value pairs."),
        "with_memory_answer": ("A Python dictionary stores key-value pairs."),
        "pairwise_reason": ("两份回答没有实质性质量差异。"),
    }


def test_end_to_end_evaluator_should_reject_invalid_agent_answer():
    case = {
        "case_id": "invalid-answer",
        "query": "Explain Python",
        "memory_context": [],
        "expected_effect": "neutral",
        "evaluation_criteria": [
            "Explain accurately.",
        ],
    }

    def fake_agent_runner(
        *,
        query,
        memory_context,
    ):
        return ""

    def fake_pairwise_judge(
        **kwargs,
    ):
        raise AssertionError("Pairwise Judge should not run")

    with pytest.raises(
        ValueError,
        match="agent answer must be",
    ):
        evaluate_memory_end_to_end_case(
            case,
            agent_runner=(fake_agent_runner),
            pairwise_judge=(fake_pairwise_judge),
        )


def test_end_to_end_evaluator_should_forward_reference_context():
    case = {
        "case_id": "harmful-memory",
        "query": "Continue learning Python",
        "memory_context": [
            {
                "memory_key": ("learning:python-mastery"),
                "content": ("The learner has fully mastered Python."),
            },
        ],
        "expected_effect": "negative",
        "evaluation_criteria": [
            ("Preserve useful foundational practice."),
        ],
        "reference_context": [
            ("The learner has not fully mastered Python."),
        ],
    }

    def fake_agent_runner(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return "Skip Python basics."

        return "Continue Python practice."

    captured = {}

    def fake_pairwise_judge(
        *,
        query,
        without_memory_answer,
        with_memory_answer,
        evaluation_criteria,
        reference_context,
    ):
        captured["reference_context"] = reference_context

        return {
            "effect": "negative",
            "reason": ("错误记忆导致跳过必要练习。"),
        }

    result = evaluate_memory_end_to_end_case(
        case,
        agent_runner=fake_agent_runner,
        pairwise_judge=(fake_pairwise_judge),
    )

    assert captured["reference_context"] == case["reference_context"]

    assert result["actual_effect"] == "negative"
