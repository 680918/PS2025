import json
from pathlib import Path
from evaluation.agent_evaluation_benchmark_comparison import (
    compare_agent_evaluation_benchmarks,
)


def save_agent_evaluation_benchmark_history(
    benchmark_result,
    output_dir,
):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_files = list(output_dir.glob("agent_evaluation_benchmark_*.json"))

    sequence_numbers = []

    for path in existing_files:
        try:
            sequence_number = int(path.stem.rsplit("_", 1)[-1])
        except ValueError:
            continue

        sequence_numbers.append(sequence_number)

    if sequence_numbers:
        next_sequence = max(sequence_numbers) + 1
    else:
        next_sequence = 1

    output_path = output_dir / (f"agent_evaluation_benchmark_{next_sequence:03d}.json")

    output_path.write_text(
        json.dumps(
            benchmark_result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output_path


def get_latest_two_agent_evaluation_benchmarks(
    output_dir,
):
    output_dir = Path(output_dir)

    if not output_dir.exists():
        return []

    benchmark_files = []

    for path in output_dir.glob("agent_evaluation_benchmark_*.json"):
        try:
            sequence_number = int(path.stem.rsplit("_", 1)[-1])
        except ValueError:
            continue

        benchmark_files.append(
            (
                sequence_number,
                path,
            )
        )

    benchmark_files.sort(key=lambda item: item[0])

    latest_files = benchmark_files[-2:]

    results = []

    for _, path in latest_files:
        results.append(json.loads(path.read_text(encoding="utf-8")))

    return results


def compare_latest_agent_evaluation_benchmarks(
    output_dir,
):
    latest_two = get_latest_two_agent_evaluation_benchmarks(output_dir)

    if len(latest_two) < 2:
        return None

    previous = latest_two[0]
    current = latest_two[1]

    return compare_agent_evaluation_benchmarks(
        previous,
        current,
    )
