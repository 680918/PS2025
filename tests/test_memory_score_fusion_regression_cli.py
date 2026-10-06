import scripts.check_memory_score_fusion_regression as cli


def test_memory_score_fusion_regression_cli_should_pass_current_baseline():
    exit_code = cli.main()

    assert exit_code == 0


def test_memory_score_fusion_regression_cli_should_fail_when_regression_detected(
    monkeypatch,
):
    monkeypatch.setattr(
        cli,
        "check_memory_score_fusion_regression",
        lambda summary: {
            "passed": False,
            "violations": [
                "minimum_pairwise_margin",
            ],
        },
    )

    exit_code = cli.main()

    assert exit_code == 1
