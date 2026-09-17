from pathlib import Path

from evaluation.agent_evaluation_batch import (
    evaluate_agent_cases,
)
from evaluation.agent_evaluation_benchmark_history import (
    compare_latest_agent_evaluation_benchmarks,
    save_agent_evaluation_benchmark_history,
)
from evaluation.agent_evaluation_benchmark_report import (
    save_agent_evaluation_benchmark_report,
)
from evaluation.agent_evaluation_cases import (
    AGENT_EVALUATION_CASES,
)
from evaluation.agent_evaluation_benchmark_comparison_report import (
    save_agent_evaluation_benchmark_comparison_report,
)


def run_agent_evaluation_benchmark_pipeline(
    output_dir,
):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    benchmark_result = evaluate_agent_cases(AGENT_EVALUATION_CASES)

    report_path = output_dir / "latest_agent_evaluation_benchmark.txt"

    save_agent_evaluation_benchmark_report(
        benchmark_result,
        report_path,
    )

    history_path = save_agent_evaluation_benchmark_history(
        benchmark_result,
        output_dir,
    )

    comparison = compare_latest_agent_evaluation_benchmarks(output_dir)

    comparison_path = None

    if comparison is not None:
        comparison_path = (
            output_dir / "latest_agent_evaluation_benchmark_comparison.txt"
        )

        save_agent_evaluation_benchmark_comparison_report(
            comparison,
            comparison_path,
        )

    return {
        "benchmark_result": benchmark_result,
        "report_path": report_path,
        "history_path": history_path,
        "comparison": comparison,
        "comparison_path": comparison_path,
    }
