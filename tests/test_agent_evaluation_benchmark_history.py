from evaluation.agent_evaluation_benchmark_history import (
    compare_latest_agent_evaluation_benchmarks,
    get_latest_two_agent_evaluation_benchmarks,
    save_agent_evaluation_benchmark_history,
)


def test_save_agent_evaluation_benchmark_history_should_increment_sequence(
    tmp_path,
):
    benchmark_result = {
        "cases": [],
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.6,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.88,
        },
    }

    first_path = save_agent_evaluation_benchmark_history(
        benchmark_result,
        tmp_path,
    )

    second_path = save_agent_evaluation_benchmark_history(
        benchmark_result,
        tmp_path,
    )

    assert first_path.name == ("agent_evaluation_benchmark_001.json")

    assert second_path.name == ("agent_evaluation_benchmark_002.json")

    assert first_path.exists()
    assert second_path.exists()


def test_get_latest_two_agent_evaluation_benchmarks(
    tmp_path,
):
    first_result = {
        "cases": [],
        "average_metrics": {
            "goal_alignment": 0.6,
            "actionability": 0.6,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.84,
        },
    }

    second_result = {
        "cases": [],
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.92,
        },
    }

    save_agent_evaluation_benchmark_history(
        first_result,
        tmp_path,
    )

    save_agent_evaluation_benchmark_history(
        second_result,
        tmp_path,
    )

    latest_two = get_latest_two_agent_evaluation_benchmarks(tmp_path)

    assert len(latest_two) == 2

    assert latest_two[0]["average_metrics"]["overall_score"] == 0.84

    assert latest_two[1]["average_metrics"]["overall_score"] == 0.92


def test_compare_latest_agent_evaluation_benchmarks(
    tmp_path,
):
    first_result = {
        "cases": [],
        "average_metrics": {
            "goal_alignment": 0.6,
            "actionability": 0.6,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.84,
        },
    }

    second_result = {
        "cases": [],
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.92,
        },
    }

    save_agent_evaluation_benchmark_history(
        first_result,
        tmp_path,
    )

    save_agent_evaluation_benchmark_history(
        second_result,
        tmp_path,
    )

    comparison = compare_latest_agent_evaluation_benchmarks(tmp_path)

    assert comparison is not None
    assert comparison["status"] == "improved"


def test_compare_latest_agent_evaluation_benchmarks_should_return_none_when_less_than_two(
    tmp_path,
):
    benchmark_result = {
        "cases": [],
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.92,
        },
    }

    save_agent_evaluation_benchmark_history(
        benchmark_result,
        tmp_path,
    )

    comparison = compare_latest_agent_evaluation_benchmarks(tmp_path)

    assert comparison is None
