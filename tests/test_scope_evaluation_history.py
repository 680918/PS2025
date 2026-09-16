import json
import pytest

from knowledge.scope_evaluation_history import (
    build_scope_history_path,
    save_scope_evaluation_history,
    get_latest_scope_history_paths,
    save_scope_evaluation_history_json,
    save_scope_evaluation_history_bundle,
    load_scope_evaluation_report_json,
    get_latest_two_scope_evaluation_reports,
    compare_latest_scope_evaluation_reports,
    save_latest_scope_evaluation_comparison,
)


def test_scope_history_should_build_first_report_path(tmp_path):
    output_dir = tmp_path / "scope_history"

    path = build_scope_history_path(output_dir)

    assert path.name == "scope_evaluation_001.txt"


def test_scope_history_should_increment_existing_report_number(tmp_path):
    output_dir = tmp_path / "scope_history"
    output_dir.mkdir()

    (output_dir / "scope_evaluation_001.txt").write_text(
        "old report",
        encoding="utf-8",
    )

    path = build_scope_history_path(output_dir)

    assert path.name == "scope_evaluation_002.txt"


def test_scope_history_should_save_report_with_incremented_name(
    tmp_path,
):
    report = {
        "summary": {
            "case_count": 1,
            "passed_count": 1,
            "failed_case_count": 0,
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 1.0,
        "failed_cases": [],
    }

    output_dir = tmp_path / "scope_history"

    first_path = save_scope_evaluation_history(
        report,
        output_dir,
    )

    second_path = save_scope_evaluation_history(
        report,
        output_dir,
    )

    assert first_path.name == "scope_evaluation_001.txt"
    assert second_path.name == "scope_evaluation_002.txt"

    assert first_path.exists()
    assert second_path.exists()

    content = first_path.read_text(
        encoding="utf-8",
    )

    assert "Knowledge Scope Evaluation Report" in content
    assert "F1: 1.0000" in content


def test_scope_history_should_return_latest_two_report_paths(
    tmp_path,
):
    output_dir = tmp_path / "scope_history"
    output_dir.mkdir()

    for number in [1, 2, 3]:
        (output_dir / f"scope_evaluation_{number:03d}.txt").write_text(
            f"report {number}",
            encoding="utf-8",
        )

    paths = get_latest_scope_history_paths(
        output_dir,
    )

    assert len(paths) == 2

    assert paths[0].name == ("scope_evaluation_002.txt")

    assert paths[1].name == ("scope_evaluation_003.txt")


def test_scope_history_should_handle_less_than_two_reports(
    tmp_path,
):
    output_dir = tmp_path / "scope_history"
    output_dir.mkdir()

    (output_dir / "scope_evaluation_001.txt").write_text(
        "report 1",
        encoding="utf-8",
    )

    paths = get_latest_scope_history_paths(
        output_dir,
    )

    assert len(paths) == 1
    assert paths[0].name == ("scope_evaluation_001.txt")


def test_scope_history_should_save_json_report(tmp_path):
    report = {
        "summary": {
            "case_count": 6,
            "passed_count": 6,
            "failed_case_count": 0,
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 1.0,
        "failed_cases": [],
    }

    output_dir = tmp_path / "scope_history"

    saved_path = save_scope_evaluation_history_json(
        report,
        output_dir,
    )

    assert saved_path.name == "scope_evaluation_001.json"
    assert saved_path.exists()

    loaded = json.loads(
        saved_path.read_text(
            encoding="utf-8",
        )
    )

    assert loaded == report


def test_scope_history_should_save_txt_and_json_with_same_number(
    tmp_path,
):
    report = {
        "summary": {
            "case_count": 1,
            "passed_count": 1,
            "failed_case_count": 0,
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 1.0,
        "failed_cases": [],
    }

    output_dir = tmp_path / "scope_history"

    result = save_scope_evaluation_history_bundle(
        report,
        output_dir,
    )

    txt_path = result["txt_path"]
    json_path = result["json_path"]

    assert txt_path.name == "scope_evaluation_001.txt"
    assert json_path.name == "scope_evaluation_001.json"

    assert txt_path.exists()
    assert json_path.exists()


def test_scope_history_should_load_json_report(tmp_path):
    report = {
        "summary": {
            "case_count": 1,
            "passed_count": 1,
            "failed_case_count": 0,
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 1.0,
        "failed_cases": [],
    }

    path = tmp_path / "scope_evaluation_001.json"

    path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    loaded = load_scope_evaluation_report_json(path)

    assert loaded == report


def test_scope_history_should_return_latest_two_json_reports(
    tmp_path,
):
    output_dir = tmp_path / "scope_history"
    output_dir.mkdir()

    for number in [1, 2, 3]:
        report = {
            "summary": {
                "average_f1": number / 10,
            }
        }

        (output_dir / f"scope_evaluation_{number:03d}.json").write_text(
            json.dumps(report),
            encoding="utf-8",
        )

    reports = get_latest_two_scope_evaluation_reports(
        output_dir,
    )

    assert len(reports) == 2

    assert reports[0]["summary"]["average_f1"] == 0.2
    assert reports[1]["summary"]["average_f1"] == 0.3


def test_scope_history_should_compare_latest_two_reports(
    tmp_path,
):
    output_dir = tmp_path / "scope_history"
    output_dir.mkdir()

    previous_report = {
        "summary": {
            "pass_rate": 0.8,
            "average_precision": 0.8,
            "average_recall": 0.8,
            "average_f1": 0.8,
        }
    }

    current_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 0.9,
            "average_recall": 0.9,
            "average_f1": 0.9,
        }
    }

    (output_dir / "scope_evaluation_001.json").write_text(
        json.dumps(previous_report),
        encoding="utf-8",
    )

    (output_dir / "scope_evaluation_002.json").write_text(
        json.dumps(current_report),
        encoding="utf-8",
    )

    result = compare_latest_scope_evaluation_reports(
        output_dir,
    )

    assert result["status"] == "improved"
    assert result["f1_delta"] == pytest.approx(0.1)


def test_scope_history_should_return_none_when_less_than_two_reports(
    tmp_path,
):
    output_dir = tmp_path / "scope_history"
    output_dir.mkdir()

    report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        }
    }

    (output_dir / "scope_evaluation_001.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    result = compare_latest_scope_evaluation_reports(
        output_dir,
    )

    assert result is None


def test_scope_history_should_save_latest_comparison(
    tmp_path,
):
    output_dir = tmp_path / "scope_history"

    previous_report = {
        "summary": {
            "case_count": 10,
            "passed_count": 8,
            "failed_case_count": 2,
            "pass_rate": 0.8,
            "average_precision": 0.8,
            "average_recall": 0.8,
            "average_f1": 0.8,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.5,
        },
        "best_score": 0.8,
        "failed_cases": [],
    }

    current_report = {
        "summary": {
            "case_count": 10,
            "passed_count": 10,
            "failed_case_count": 0,
            "pass_rate": 1.0,
            "average_precision": 0.9,
            "average_recall": 0.9,
            "average_f1": 0.9,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 0.9,
        "failed_cases": [],
    }

    save_scope_evaluation_history_bundle(
        previous_report,
        output_dir,
    )

    save_scope_evaluation_history_bundle(
        current_report,
        output_dir,
    )

    comparison_path = tmp_path / "reports" / "latest_scope_comparison.txt"

    saved_path = save_latest_scope_evaluation_comparison(
        output_dir=output_dir,
        comparison_path=comparison_path,
    )

    assert saved_path == comparison_path
    assert comparison_path.exists()

    content = comparison_path.read_text(
        encoding="utf-8",
    )

    assert "Knowledge Scope Regression Comparison" in content
    assert "Status: improved" in content
    assert "F1 delta: +0.1000" in content


def test_scope_history_should_not_save_comparison_with_less_than_two_reports(
    tmp_path,
):
    output_dir = tmp_path / "scope_history"

    report = {
        "summary": {
            "case_count": 10,
            "passed_count": 10,
            "failed_case_count": 0,
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 1.0,
        "failed_cases": [],
    }

    save_scope_evaluation_history_bundle(
        report,
        output_dir,
    )

    comparison_path = tmp_path / "reports" / "latest_scope_comparison.txt"

    saved_path = save_latest_scope_evaluation_comparison(
        output_dir=output_dir,
        comparison_path=comparison_path,
    )

    assert saved_path is None
    assert not comparison_path.exists()
