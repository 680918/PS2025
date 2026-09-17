from evaluation.agent_evaluation_benchmark_comparison_report import (
    render_agent_evaluation_benchmark_comparison,
    save_agent_evaluation_benchmark_comparison_report,
)


def test_render_agent_evaluation_benchmark_comparison():
    comparison = {
        "status": "improved",
        "goal_alignment_delta": 0.2,
        "actionability_delta": 0.1,
        "memory_usage_delta": 0.0,
        "knowledge_usage_delta": -0.1,
        "response_policy_delta": 0.0,
        "overall_score_delta": 0.04,
    }

    report = render_agent_evaluation_benchmark_comparison(comparison)

    assert "Agent Evaluation Benchmark Comparison" in report

    assert "Status: improved" in report
    assert "Goal alignment delta: +0.2000" in report
    assert "Actionability delta: +0.1000" in report
    assert "Memory usage delta: +0.0000" in report
    assert "Knowledge usage delta: -0.1000" in report
    assert "Response policy delta: +0.0000" in report
    assert "Overall score delta: +0.0400" in report


def test_save_agent_evaluation_benchmark_comparison_report(
    tmp_path,
):
    comparison = {
        "status": "improved",
        "goal_alignment_delta": 0.2,
        "actionability_delta": 0.1,
        "memory_usage_delta": 0.0,
        "knowledge_usage_delta": -0.1,
        "response_policy_delta": 0.0,
        "overall_score_delta": 0.04,
    }

    output_path = tmp_path / "latest_agent_evaluation_benchmark_comparison.txt"

    saved_path = save_agent_evaluation_benchmark_comparison_report(
        comparison,
        output_path,
    )

    assert saved_path == output_path
    assert output_path.exists()

    content = output_path.read_text(encoding="utf-8")

    assert "Status: improved" in content
    assert "Overall score delta: +0.0400" in content
