from evaluation.agent_evaluation_report import (
    render_agent_evaluation_comparison,
    save_agent_evaluation_comparison_report,
)


def test_agent_evaluation_comparison_report_should_render_metrics():
    comparison = {
        "status": "improved",
        "goal_alignment_delta": 0.2,
        "actionability_delta": 0.1,
        "memory_usage_delta": 0.0,
        "knowledge_usage_delta": -0.1,
        "response_policy_delta": 0.0,
        "overall_score_delta": 0.04,
    }

    text = render_agent_evaluation_comparison(comparison)

    assert "Agent Evaluation Regression Comparison" in text
    assert "Status: improved" in text
    assert "Goal alignment delta: +0.2000" in text
    assert "Knowledge usage delta: -0.1000" in text
    assert "Overall score delta: +0.0400" in text


def test_agent_evaluation_comparison_report_should_save_file(
    tmp_path,
):
    comparison = {
        "status": "regressed",
        "goal_alignment_delta": -0.2,
        "actionability_delta": 0.0,
        "memory_usage_delta": -0.1,
        "knowledge_usage_delta": 0.0,
        "response_policy_delta": 0.0,
        "overall_score_delta": -0.06,
    }

    output_path = tmp_path / "reports" / "agent_evaluation_comparison.txt"

    saved_path = save_agent_evaluation_comparison_report(
        comparison,
        output_path,
    )

    assert saved_path == output_path
    assert output_path.exists()

    content = output_path.read_text(
        encoding="utf-8",
    )

    assert "Agent Evaluation Regression Comparison" in content
    assert "Status: regressed" in content
    assert "Overall score delta: -0.0600" in content
