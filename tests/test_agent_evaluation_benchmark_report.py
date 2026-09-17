from evaluation.agent_evaluation_benchmark_report import (
    render_agent_evaluation_benchmark_report,
    save_agent_evaluation_benchmark_report,
)


def test_render_agent_evaluation_benchmark_report():
    benchmark_result = {
        "cases": [
            {
                "case_id": "case_001",
                "focus_metric": "goal_alignment",
                "evaluation_result": {
                    "overall_score": 0.8,
                },
            },
            {
                "case_id": "case_002",
                "focus_metric": "actionability",
                "evaluation_result": {
                    "overall_score": 0.6,
                },
            },
        ],
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.6,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.88,
        },
    }

    report = render_agent_evaluation_benchmark_report(benchmark_result)

    assert "Agent Evaluation Benchmark Report" in report
    assert "Cases: 2" in report
    assert "Goal alignment: 0.8000" in report
    assert "Actionability: 0.6000" in report
    assert "Memory usage: 1.0000" in report
    assert "Knowledge usage: 1.0000" in report
    assert "Response policy: 1.0000" in report
    assert "Overall score: 0.8800" in report


def test_save_agent_evaluation_benchmark_report(
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

    output_path = tmp_path / "agent_evaluation_benchmark.txt"

    saved_path = save_agent_evaluation_benchmark_report(
        benchmark_result,
        output_path,
    )

    assert saved_path == output_path
    assert output_path.exists()

    content = output_path.read_text(encoding="utf-8")

    assert "Agent Evaluation Benchmark Report" in content

    assert "Overall score: 0.8800" in content
