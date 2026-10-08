from memory.memory_contribution_benchmark import (
    run_memory_contribution_benchmark,
)


def main():
    report = run_memory_contribution_benchmark()

    summary = report["summary"]

    print("Memory Contribution Benchmark")
    print()
    print(f"total_cases: {summary['total_cases']}")
    print(f"passed_cases: {summary['passed_cases']}")
    print(f"failed_cases: {summary['failed_cases']}")
    print(f"accuracy: {summary['accuracy']:.2f}")
    print()

    for result in report["results"]:
        status = "PASS" if result["passed"] else "FAIL"

        print(
            f"{result['case_id']}: "
            f"{status} "
            f"expected={result['expected_effect']} "
            f"actual={result['actual_effect']} "
            f"delta={result['contribution_delta']:.2f}"
        )


if __name__ == "__main__":
    main()
