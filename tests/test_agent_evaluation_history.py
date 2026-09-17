import json

from evaluation.agent_evaluation_history import (
    compare_latest_agent_evaluations,
    get_latest_two_agent_evaluations,
    save_agent_evaluation_history,
)


def test_agent_evaluation_history_should_save_json(tmp_path):
    evaluation_result = {
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

    saved_path = save_agent_evaluation_history(
        evaluation_result,
        tmp_path,
    )

    assert saved_path.name == "agent_evaluation_001.json"
    assert saved_path.exists()

    loaded = json.loads(
        saved_path.read_text(
            encoding="utf-8",
        )
    )

    assert loaded == evaluation_result


def test_agent_evaluation_history_should_increment_sequence(
    tmp_path,
):
    evaluation_result = {
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

    first_path = save_agent_evaluation_history(
        evaluation_result,
        tmp_path,
    )

    second_path = save_agent_evaluation_history(
        evaluation_result,
        tmp_path,
    )

    assert first_path.name == "agent_evaluation_001.json"
    assert second_path.name == "agent_evaluation_002.json"


def test_agent_evaluation_history_should_return_latest_two_results(
    tmp_path,
):
    for score in [0.6, 0.8, 1.0]:
        evaluation_result = {
            "goal_alignment": score,
            "actionability": score,
            "memory_usage": score,
            "knowledge_usage": score,
            "response_policy": score,
            "overall_score": score,
            "passed": score >= 0.5,
            "findings": [],
            "improvement_suggestions": [],
        }

        save_agent_evaluation_history(
            evaluation_result,
            tmp_path,
        )

    results = get_latest_two_agent_evaluations(
        tmp_path,
    )

    assert len(results) == 2

    assert results[0]["overall_score"] == 0.8
    assert results[1]["overall_score"] == 1.0


def test_agent_evaluation_history_should_return_empty_when_no_history(
    tmp_path,
):
    results = get_latest_two_agent_evaluations(
        tmp_path,
    )

    assert results == []


def test_agent_evaluation_history_should_compare_latest_two_results(
    tmp_path,
):
    previous = {
        "goal_alignment": 0.8,
        "actionability": 0.8,
        "memory_usage": 0.8,
        "knowledge_usage": 0.8,
        "response_policy": 1.0,
        "overall_score": 0.84,
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

    save_agent_evaluation_history(
        previous,
        tmp_path,
    )

    save_agent_evaluation_history(
        current,
        tmp_path,
    )

    result = compare_latest_agent_evaluations(
        tmp_path,
    )

    assert result["status"] == "improved"
    assert result["overall_score_delta"] > 0


def test_agent_evaluation_history_should_return_none_when_less_than_two_results(
    tmp_path,
):
    evaluation_result = {
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

    save_agent_evaluation_history(
        evaluation_result,
        tmp_path,
    )

    result = compare_latest_agent_evaluations(
        tmp_path,
    )

    assert result is None
