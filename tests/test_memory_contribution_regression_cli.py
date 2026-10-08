from scripts.check_memory_contribution_regression import (
    main,
)


def test_memory_contribution_regression_cli_should_pass_current_baseline():
    exit_code = main()

    assert exit_code == 0
