import json
from pathlib import Path
from knowledge.scope_evaluation_report import (
    save_scope_evaluation_report,
    render_scope_evaluation_report,
)
from knowledge.scope_evaluation_comparison import (
    compare_scope_evaluation_reports,
    save_scope_evaluation_comparison,
)


def build_scope_history_path(output_dir):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_numbers = []

    for path in output_dir.glob("scope_evaluation_*.txt"):
        stem = path.stem

        number_text = stem.replace(
            "scope_evaluation_",
            "",
        )

        if number_text.isdigit():
            existing_numbers.append(int(number_text))

    if existing_numbers:
        next_number = max(existing_numbers) + 1
    else:
        next_number = 1

    filename = f"scope_evaluation_{next_number:03d}.txt"

    return output_dir / filename


def save_scope_evaluation_history(
    report,
    output_dir,
):
    output_path = build_scope_history_path(
        output_dir,
    )

    return save_scope_evaluation_report(
        report,
        output_path,
    )


def get_latest_scope_history_paths(
    output_dir,
):
    output_dir = Path(output_dir)

    if not output_dir.exists():
        return []

    numbered_paths = []

    for path in output_dir.glob("scope_evaluation_*.txt"):
        number_text = path.stem.replace(
            "scope_evaluation_",
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

    paths = [path for _, path in numbered_paths]

    return paths[-2:]


def save_scope_evaluation_history_json(
    report,
    output_dir,
):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_numbers = []

    for path in output_dir.glob("scope_evaluation_*.json"):
        number_text = path.stem.replace(
            "scope_evaluation_",
            "",
        )

        if number_text.isdigit():
            existing_numbers.append(int(number_text))

    if existing_numbers:
        next_number = max(existing_numbers) + 1
    else:
        next_number = 1

    output_path = output_dir / f"scope_evaluation_{next_number:03d}.json"

    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output_path


def save_scope_evaluation_history_bundle(
    report,
    output_dir,
):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_numbers = []

    for path in output_dir.glob("scope_evaluation_*.*"):
        if path.suffix not in {
            ".txt",
            ".json",
        }:
            continue

        number_text = path.stem.replace(
            "scope_evaluation_",
            "",
        )

        if number_text.isdigit():
            existing_numbers.append(int(number_text))

    if existing_numbers:
        next_number = max(existing_numbers) + 1
    else:
        next_number = 1

    base_name = f"scope_evaluation_{next_number:03d}"

    txt_path = output_dir / f"{base_name}.txt"
    json_path = output_dir / f"{base_name}.json"

    txt_path.write_text(
        render_scope_evaluation_report(report),
        encoding="utf-8",
    )

    json_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "txt_path": txt_path,
        "json_path": json_path,
    }


def load_scope_evaluation_report_json(path):
    path = Path(path)

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def get_latest_two_scope_evaluation_reports(
    output_dir,
):
    output_dir = Path(output_dir)

    if not output_dir.exists():
        return []

    numbered_paths = []

    for path in output_dir.glob("scope_evaluation_*.json"):
        number_text = path.stem.replace(
            "scope_evaluation_",
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

    return [load_scope_evaluation_report_json(path) for path in latest_paths]


def compare_latest_scope_evaluation_reports(
    output_dir,
):
    reports = get_latest_two_scope_evaluation_reports(
        output_dir,
    )

    if len(reports) < 2:
        return None

    previous_report, current_report = reports

    return compare_scope_evaluation_reports(
        previous_report=previous_report,
        current_report=current_report,
    )


def save_latest_scope_evaluation_comparison(
    output_dir,
    comparison_path,
):
    comparison = compare_latest_scope_evaluation_reports(
        output_dir,
    )

    if comparison is None:
        return None

    return save_scope_evaluation_comparison(
        comparison,
        comparison_path,
    )
