import json
import argparse

from pathlib import Path
from evaluation.agent_evaluation_benchmark_comparison import (
    compare_agent_evaluation_benchmarks,
)
from evaluation.agent_evaluation_benchmark_pipeline import (
    run_agent_evaluation_benchmark_pipeline,
)

DEFAULT_OUTPUT_DIR = Path("reports/agent_evaluation_benchmark")


def run_benchmark_cli(
    output_dir,
    baseline_path=None,
):
    result = run_agent_evaluation_benchmark_pipeline(
        output_dir=output_dir,
    )

    benchmark_result = result["benchmark_result"]

    overall_score = benchmark_result["average_metrics"]["overall_score"]

    if baseline_path is not None:
        baseline_path = Path(baseline_path)

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

        comparison = compare_agent_evaluation_benchmarks(
            baseline,
            benchmark_result,
        )
    else:
        comparison = result["comparison"]

    if comparison is None:
        status = "no_comparison"
    else:
        status = comparison["status"]

    print(f"Overall score: {overall_score:.4f}")

    print(f"Status: {status}")

    if status == "regressed":
        return 1

    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
    )

    args = parser.parse_args(argv)

    exit_code = run_benchmark_cli(
        output_dir=DEFAULT_OUTPUT_DIR,
        baseline_path=args.baseline,
    )

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
