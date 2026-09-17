import pytest
from evaluation.agent_evaluation_comparison import (
    compare_agent_evaluations,
)


def test_agent_evaluation_comparison_should_detect_improvement():
    previous = {
        "goal_alignment": 0.6,
        "actionability": 0.8,
        "memory_usage": 0.8,
        "knowledge_usage": 0.8,
        "response_policy": 1.0,
        "overall_score": 0.8,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    current = {
        "goal_alignment": 1.0,
        "actionability": 1.0,
        "memory_usage": 1.0,
        "knowledge_usage": 1.0,
        "response_policy": 1.0,
        "overall_score": 1.0,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    result = compare_agent_evaluations(
        previous,
        current,
    )

    assert result["status"] == "improved"
    assert result["overall_score_delta"] == pytest.approx(0.2)


def test_agent_evaluation_comparison_should_detect_regression():
    previous = {
        "goal_alignment": 1.0,
        "actionability": 1.0,
        "memory_usage": 1.0,
        "knowledge_usage": 1.0,
        "response_policy": 1.0,
        "overall_score": 1.0,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    current = {
        "goal_alignment": 0.6,
        "actionability": 0.8,
        "memory_usage": 0.8,
        "knowledge_usage": 0.8,
        "response_policy": 1.0,
        "overall_score": 0.8,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    result = compare_agent_evaluations(
        previous,
        current,
    )

    assert result["status"] == "regressed"
    assert result["overall_score_delta"] == pytest.approx(-0.2)


def test_agent_evaluation_comparison_should_detect_unchanged():
    previous = {
        "goal_alignment": 1.0,
        "actionability": 1.0,
        "memory_usage": 1.0,
        "knowledge_usage": 1.0,
        "response_policy": 1.0,
        "overall_score": 1.0,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    current = previous.copy()

    result = compare_agent_evaluations(
        previous,
        current,
    )

    assert result["status"] == "unchanged"
    assert result["overall_score_delta"] == pytest.approx(0.0)


def test_agent_evaluation_comparison_should_return_metric_deltas():
    previous = {
        "goal_alignment": 0.6,
        "actionability": 0.8,
        "memory_usage": 0.7,
        "knowledge_usage": 0.9,
        "response_policy": 1.0,
        "overall_score": 0.8,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    current = {
        "goal_alignment": 0.8,
        "actionability": 1.0,
        "memory_usage": 0.9,
        "knowledge_usage": 0.8,
        "response_policy": 1.0,
        "overall_score": 0.9,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    result = compare_agent_evaluations(
        previous,
        current,
    )

    assert result["goal_alignment_delta"] == pytest.approx(0.2)
    assert result["actionability_delta"] == pytest.approx(0.2)
    assert result["memory_usage_delta"] == pytest.approx(0.2)
    assert result["knowledge_usage_delta"] == pytest.approx(-0.1)
    assert result["response_policy_delta"] == pytest.approx(0.0)
    assert result["overall_score_delta"] == pytest.approx(0.1)
