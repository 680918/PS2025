from memory.memory_contribution_benchmark import (
    run_memory_contribution_benchmark,
)
from memory.memory_contribution_regression import (
    evaluate_memory_contribution_regression,
)


def main():
    report = run_memory_contribution_benchmark()

    regression = evaluate_memory_contribution_regression(report)

    print("Memory Contribution Regression")
    print()

    print("status: " + ("PASS" if regression["passed"] else "FAIL"))

    print(f"accuracy: {report['summary']['accuracy']:.2f}")

    if regression["failures"]:
        print()
        print("failures:")

        for failure in regression["failures"]:
            print(f"- {failure}")

    return 0 if regression["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
