import json
from pathlib import Path
from evaluation.agent_evaluation_comparison import (
    compare_agent_evaluations,
)


def save_agent_evaluation_history(
    evaluation_result,
    output_dir,
):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_numbers = []

    for path in output_dir.glob("agent_evaluation_*.json"):
        number_text = path.stem.replace(
            "agent_evaluation_",
            "",
        )

        if number_text.isdigit():
            existing_numbers.append(int(number_text))

    if existing_numbers:
        next_number = max(existing_numbers) + 1
    else:
        next_number = 1

    output_path = output_dir / f"agent_evaluation_{next_number:03d}.json"

    output_path.write_text(
        json.dumps(
            evaluation_result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output_path


def get_latest_two_agent_evaluations(
    output_dir,
):
    output_dir = Path(output_dir)

    if not output_dir.exists():
        return []

    numbered_paths = []

    for path in output_dir.glob("agent_evaluation_*.json"):
        number_text = path.stem.replace(
            "agent_evaluation_",
            "",
        )

        if number_text.isdigit():
            numbered_paths.append(
                (
                    int(number_text),
                    path,
                )
            )

    numbered_paths.sort(key=lambda item: item[0])

    latest_paths = [path for _, path in numbered_paths[-2:]]

    return [
        json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
        for path in latest_paths
    ]


def compare_latest_agent_evaluations(
    output_dir,
):
    evaluations = get_latest_two_agent_evaluations(
        output_dir,
    )

    if len(evaluations) < 2:
        return None

    previous, current = evaluations

    return compare_agent_evaluations(
        previous,
        current,
    )
