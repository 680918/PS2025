from memory.memory_conflict_resolution_dataset import (
    get_memory_conflict_resolution_cases,
)
from memory.memory_conflict_resolution_runner import (
    run_memory_conflict_resolution_evaluation,
)


def main():
    report = run_memory_conflict_resolution_evaluation(
        get_memory_conflict_resolution_cases()
    )

    summary = report["summary"]

    print("=" * 64)
    print("Memory Conflict Resolution Evaluation v1")
    print("=" * 64)
    print()
    print(f"案例数: {summary['total_cases']}")
    print(f"正确: {summary['correct_cases']}")
    print(f"错误: {summary['error_cases']}")
    print(f"准确率: {summary['accuracy']:.1%}")

    for (
        category,
        category_summary,
    ) in report["category_summary"].items():
        print()
        print(
            f"{category}: "
            f"{category_summary['correct_cases']}/"
            f"{category_summary['total_cases']} "
            f"({category_summary['accuracy']:.1%})"
        )

    print()

    for result in report["errors"]:
        print("-" * 64)
        print(f"案例: {result['case_id']}")
        print(
            f"Expected: {result['expected_resolution']} / {result['expected_reason']}"
        )
        print(f"Actual: {result['actual_resolution']} / {result['actual_reason']}")


if __name__ == "__main__":
    main()
