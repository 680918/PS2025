from scripts.check_memory_relevance_calibration import (
    get_calibration_check_exit_code,
    main,
    run_calibration_check,
)


def test_calibration_check_should_return_zero_when_regression_passes():
    result = {
        "passed": True,
        "regressions": [],
    }

    exit_code = get_calibration_check_exit_code(
        result,
    )

    assert exit_code == 0


def test_calibration_check_should_return_one_when_regression_fails():
    result = {
        "passed": False,
        "regressions": [
            "minimum_pairwise_margin",
        ],
    }

    exit_code = get_calibration_check_exit_code(
        result,
    )

    assert exit_code == 1


def test_current_calibration_check_should_pass():
    result = run_calibration_check()

    assert result["passed"] is True

    exit_code = get_calibration_check_exit_code(
        result,
    )

    assert exit_code == 0


def test_calibration_check_main_should_return_zero_for_current_calibration():
    exit_code = main()

    assert exit_code == 0
