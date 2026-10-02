from memory.retrieval_benchmark_runner import (
    run_retrieval_benchmark,
)

from memory.retrieval_benchmark_report import (
    summarize_benchmark_results,
)

from memory.retrieval_benchmark_cli import (
    format_benchmark_report,
)


def build_benchmark_output(
    threshold=None,
    score_gap_threshold=None,
):

    results = run_retrieval_benchmark(
        k_values=[1, 2, 3],
        threshold=threshold,
        score_gap_threshold=score_gap_threshold,
    )

    report = summarize_benchmark_results(results)

    return format_benchmark_report(report)


def main():

    output = build_benchmark_output(
        threshold=0.5,
        score_gap_threshold=0.4,
    )

    print(output)


if __name__ == "__main__":
    main()
