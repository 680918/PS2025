from memory.relevance_calibration_runner import (
    run_relevance_calibration_regression,
)


def get_calibration_check_exit_code(
    result,
):
    if result.get("passed"):
        return 0

    return 1


def run_calibration_check():
    return run_relevance_calibration_regression()


def main():
    result = run_calibration_check()

    return get_calibration_check_exit_code(
        result,
    )


if __name__ == "__main__":
    raise SystemExit(main())
