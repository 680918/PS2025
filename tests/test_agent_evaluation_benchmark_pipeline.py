from evaluation.agent_evaluation_benchmark_pipeline import (
    run_agent_evaluation_benchmark_pipeline,
)


def test_run_agent_evaluation_benchmark_pipeline(
    tmp_path,
):
    result = run_agent_evaluation_benchmark_pipeline(
        output_dir=tmp_path,
    )

    assert "benchmark_result" in result
    assert "report_path" in result
    assert "history_path" in result
    assert "comparison" in result
    assert "comparison_path" in result

    assert result["report_path"].exists()
    assert result["history_path"].exists()

    assert result["comparison"] is None
    assert result["comparison_path"] is None


def test_run_agent_evaluation_benchmark_pipeline_should_compare_second_run(
    tmp_path,
):
    first_result = run_agent_evaluation_benchmark_pipeline(
        output_dir=tmp_path,
    )

    second_result = run_agent_evaluation_benchmark_pipeline(
        output_dir=tmp_path,
    )

    assert first_result["comparison"] is None
    assert first_result["comparison_path"] is None

    assert second_result["comparison"] is not None

    assert second_result["comparison"]["status"] in {
        "improved",
        "regressed",
        "unchanged",
    }

    assert second_result["comparison_path"] is not None
    assert second_result["comparison_path"].exists()
