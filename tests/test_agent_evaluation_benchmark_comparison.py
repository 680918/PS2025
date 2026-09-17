import pytest

from evaluation.agent_evaluation_benchmark_comparison import (
    compare_agent_evaluation_benchmarks,
)


def test_compare_agent_evaluation_benchmarks_should_detect_improvement():
    previous = {
        "average_metrics": {
            "goal_alignment": 0.6,
            "actionability": 0.6,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.84,
        }
    }

    current = {
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.92,
        }
    }

    comparison = compare_agent_evaluation_benchmarks(
        previous,
        current,
    )

    assert comparison["status"] == "improved"

    assert comparison["overall_score_delta"] == pytest.approx(0.08)

    assert comparison["goal_alignment_delta"] == pytest.approx(0.2)

    assert comparison["actionability_delta"] == pytest.approx(0.2)


def test_compare_agent_evaluation_benchmarks_should_detect_regression():
    previous = {
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.92,
        }
    }

    current = {
        "average_metrics": {
            "goal_alignment": 0.6,
            "actionability": 0.6,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.84,
        }
    }

    comparison = compare_agent_evaluation_benchmarks(
        previous,
        current,
    )

    assert comparison["status"] == "regressed"


def test_compare_agent_evaluation_benchmarks_should_detect_unchanged():
    previous = {
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.92,
        }
    }

    current = {
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.92,
        }
    }

    comparison = compare_agent_evaluation_benchmarks(
        previous,
        current,
    )

    assert comparison["status"] == "unchanged"


def test_compare_agent_evaluation_benchmarks_should_respect_tolerance():
    previous = {
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.9000000000,
        }
    }

    current = {
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.9000000005,
        }
    }

    comparison = compare_agent_evaluation_benchmarks(
        previous,
        current,
        tolerance=1e-9,
    )

    assert comparison["status"] == "unchanged"
