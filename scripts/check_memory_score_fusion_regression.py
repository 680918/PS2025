from memory.memory_score_fusion_benchmark import (
    run_memory_score_fusion_benchmark,
    summarize_memory_score_fusion_benchmark,
)
from memory.memory_score_fusion_regression import (
    check_memory_score_fusion_regression,
)


def main():
    results = run_memory_score_fusion_benchmark()

    summary = summarize_memory_score_fusion_benchmark(
        results,
    )

    regression = check_memory_score_fusion_regression(
        summary,
    )

    if regression["passed"]:
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
