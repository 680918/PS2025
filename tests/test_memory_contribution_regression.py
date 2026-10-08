from copy import deepcopy

from memory.memory_contribution_benchmark import (
    run_memory_contribution_benchmark,
)
from memory.memory_contribution_regression import (
    evaluate_memory_contribution_regression,
)


def test_current_contribution_benchmark_should_match_regression_baseline():
    report = run_memory_contribution_benchmark()

    regression = evaluate_memory_contribution_regression(report)

    assert regression["passed"] is True
    assert regression["failures"] == []


def test_contribution_regression_should_fail_when_accuracy_drops():
    report = run_memory_contribution_benchmark()

    report = deepcopy(report)

    report["summary"]["accuracy"] = 2 / 3

    regression = evaluate_memory_contribution_regression(report)

    assert regression["passed"] is False

    assert any("accuracy" in failure for failure in regression["failures"])


def test_contribution_regression_should_fail_when_case_delta_changes():
    report = run_memory_contribution_benchmark()

    report = deepcopy(report)

    report["results"][0]["contribution_delta"] = 0.10

    regression = evaluate_memory_contribution_regression(report)

    assert regression["passed"] is False

    assert any("contribution_delta" in failure for failure in regression["failures"])


def test_contribution_regression_should_fail_when_case_is_missing():
    report = run_memory_contribution_benchmark()

    report = deepcopy(report)

    report["results"] = report["results"][:-1]

    regression = evaluate_memory_contribution_regression(report)

    assert regression["passed"] is False

    assert any("missing case" in failure for failure in regression["failures"])
