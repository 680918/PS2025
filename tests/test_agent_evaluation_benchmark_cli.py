from evaluation.agent_evaluation_benchmark_cli import (
    main,
    run_benchmark_cli,
)


def test_run_benchmark_cli_should_return_zero_when_not_regressed(
    tmp_path,
    monkeypatch,
):
    def fake_pipeline(output_dir):
        return {
            "benchmark_result": {
                "average_metrics": {
                    "overall_score": 0.88,
                }
            },
            "comparison": {
                "status": "improved",
            },
            "report_path": tmp_path / "benchmark.txt",
            "history_path": tmp_path / "history.json",
            "comparison_path": tmp_path / "comparison.txt",
        }

    monkeypatch.setattr(
        "evaluation.agent_evaluation_benchmark_cli."
        "run_agent_evaluation_benchmark_pipeline",
        fake_pipeline,
    )

    exit_code = run_benchmark_cli(output_dir=tmp_path)

    assert exit_code == 0


def test_run_benchmark_cli_should_return_nonzero_when_regressed(
    tmp_path,
    monkeypatch,
):
    def fake_pipeline(output_dir):
        return {
            "benchmark_result": {
                "average_metrics": {
                    "overall_score": 0.72,
                }
            },
            "comparison": {
                "status": "regressed",
            },
            "report_path": tmp_path / "benchmark.txt",
            "history_path": tmp_path / "history.json",
            "comparison_path": tmp_path / "comparison.txt",
        }

    monkeypatch.setattr(
        "evaluation.agent_evaluation_benchmark_cli."
        "run_agent_evaluation_benchmark_pipeline",
        fake_pipeline,
    )

    exit_code = run_benchmark_cli(output_dir=tmp_path)

    assert exit_code == 1


def test_main_should_exit_with_benchmark_exit_code(
    monkeypatch,
):
    def fake_run_benchmark_cli(
        output_dir,
        baseline_path=None,
    ):
        return 1

    monkeypatch.setattr(
        "evaluation.agent_evaluation_benchmark_cli.run_benchmark_cli",
        fake_run_benchmark_cli,
    )

    try:
        main([])
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("main() should raise SystemExit")


def test_run_benchmark_cli_should_print_score_and_status(
    tmp_path,
    monkeypatch,
    capsys,
):
    def fake_pipeline(output_dir):
        return {
            "benchmark_result": {
                "average_metrics": {
                    "overall_score": 0.88,
                }
            },
            "comparison": {
                "status": "unchanged",
            },
            "report_path": tmp_path / "benchmark.txt",
            "history_path": tmp_path / "history.json",
            "comparison_path": tmp_path / "comparison.txt",
        }

    monkeypatch.setattr(
        "evaluation.agent_evaluation_benchmark_cli."
        "run_agent_evaluation_benchmark_pipeline",
        fake_pipeline,
    )

    exit_code = run_benchmark_cli(output_dir=tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Overall score: 0.8800" in captured.out
    assert "Status: unchanged" in captured.out


def test_run_benchmark_cli_should_compare_against_baseline(
    tmp_path,
    monkeypatch,
):
    baseline = {
        "average_metrics": {
            "goal_alignment": 0.8,
            "actionability": 0.8,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.90,
        }
    }

    current = {
        "cases": [],
        "average_metrics": {
            "goal_alignment": 0.6,
            "actionability": 0.6,
            "memory_usage": 1.0,
            "knowledge_usage": 1.0,
            "response_policy": 1.0,
            "overall_score": 0.82,
        },
    }

    baseline_path = tmp_path / "baseline.json"

    import json

    baseline_path.write_text(
        json.dumps(baseline),
        encoding="utf-8",
    )

    def fake_pipeline(output_dir):
        return {
            "benchmark_result": current,
            "comparison": None,
            "report_path": tmp_path / "benchmark.txt",
            "history_path": tmp_path / "history.json",
            "comparison_path": None,
        }

    monkeypatch.setattr(
        "evaluation.agent_evaluation_benchmark_cli."
        "run_agent_evaluation_benchmark_pipeline",
        fake_pipeline,
    )

    exit_code = run_benchmark_cli(
        output_dir=tmp_path,
        baseline_path=baseline_path,
    )

    assert exit_code == 1


def test_main_should_pass_baseline_argument_to_cli(
    monkeypatch,
    tmp_path,
):
    baseline_path = tmp_path / "baseline.json"

    captured = {}

    def fake_run_benchmark_cli(
        output_dir,
        baseline_path=None,
    ):
        captured["output_dir"] = output_dir
        captured["baseline_path"] = baseline_path
        return 0

    monkeypatch.setattr(
        "evaluation.agent_evaluation_benchmark_cli.run_benchmark_cli",
        fake_run_benchmark_cli,
    )

    try:
        main(
            [
                "--baseline",
                str(baseline_path),
            ]
        )
    except SystemExit as exc:
        assert exc.code == 0

    assert captured["baseline_path"] == baseline_path
