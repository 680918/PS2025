from knowledge.scope_evaluation_report import (
    build_scope_evaluation_report,
    render_scope_evaluation_report,
    save_scope_evaluation_report,
)


def test_scope_evaluation_report_should_build_summary():
    batch_result = {
        "case_count": 6,
        "passed_count": 5,
        "average_precision": 1.0,
        "average_recall": 0.9166666666666666,
        "average_f1": 0.9444444444444445,
        "results": [],
    }

    tuning_result = {
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 1.0,
        "trials": [],
    }

    report = build_scope_evaluation_report(
        batch_result=batch_result,
        tuning_result=tuning_result,
    )

    assert report["summary"]["case_count"] == 6
    assert report["summary"]["passed_count"] == 5
    assert report["summary"]["pass_rate"] == 5 / 6

    assert report["summary"]["average_precision"] == 1.0
    assert report["summary"]["average_recall"] == 0.9166666666666666
    assert report["summary"]["average_f1"] == 0.9444444444444445

    assert report["best_parameters"] == {
        "top_n": 2,
        "min_score": 2,
        "min_relative_score": 0.6,
    }

    assert report["best_score"] == 1.0


def test_scope_evaluation_report_should_include_failed_cases():
    batch_result = {
        "case_count": 2,
        "passed_count": 1,
        "average_precision": 0.75,
        "average_recall": 1.0,
        "average_f1": 0.8333333333333333,
        "results": [
            {
                "name": "strong_agent_title_match",
                "query": "agent tool",
                "expected_document_ids": ["doc-agent"],
                "actual_document_ids": ["doc-agent", "doc-memory"],
                "passed": False,
                "precision": 0.5,
                "recall": 1.0,
                "f1": 0.6666666666666666,
            },
            {
                "name": "strong_system_title_match",
                "query": "system thinking",
                "expected_document_ids": ["doc-system"],
                "actual_document_ids": ["doc-system"],
                "passed": True,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
            },
        ],
    }

    tuning_result = {
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 1.0,
        "trials": [],
    }

    report = build_scope_evaluation_report(
        batch_result=batch_result,
        tuning_result=tuning_result,
    )

    assert len(report["failed_cases"]) == 1

    assert report["failed_cases"][0]["name"] == ("strong_agent_title_match")


def test_scope_evaluation_report_should_include_pass_rate_and_failed_count():
    batch_result = {
        "case_count": 4,
        "passed_count": 3,
        "average_precision": 0.9,
        "average_recall": 0.8,
        "average_f1": 0.85,
        "results": [
            {
                "name": "case-1",
                "passed": True,
            },
            {
                "name": "case-2",
                "passed": True,
            },
            {
                "name": "case-3",
                "passed": True,
            },
            {
                "name": "case-4",
                "passed": False,
            },
        ],
    }

    tuning_result = {
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 0.85,
        "trials": [],
    }

    report = build_scope_evaluation_report(
        batch_result=batch_result,
        tuning_result=tuning_result,
    )

    assert report["summary"]["pass_rate"] == 0.75
    assert report["summary"]["failed_case_count"] == 1


def test_scope_evaluation_report_should_handle_empty_batch():
    batch_result = {
        "case_count": 0,
        "passed_count": 0,
        "average_precision": 1.0,
        "average_recall": 1.0,
        "average_f1": 1.0,
        "results": [],
    }

    tuning_result = {
        "best_parameters": None,
        "best_score": None,
        "trials": [],
    }

    report = build_scope_evaluation_report(
        batch_result=batch_result,
        tuning_result=tuning_result,
    )

    assert report["summary"]["pass_rate"] == 1.0
    assert report["summary"]["failed_case_count"] == 0


def test_scope_evaluation_report_should_render_readable_text():
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

    text = render_scope_evaluation_report(report)

    assert "Knowledge Scope Evaluation Report" in text
    assert "Cases: 6" in text
    assert "Passed: 6" in text
    assert "Failed: 0" in text
    assert "Pass rate: 100.00%" in text
    assert "Precision: 1.0000" in text
    assert "Recall: 1.0000" in text
    assert "F1: 1.0000" in text
    assert "top_n: 2" in text
    assert "min_score: 2" in text
    assert "min_relative_score: 0.6" in text
    assert "Failed cases: None" in text


def test_scope_evaluation_report_should_render_failed_cases():
    report = {
        "summary": {
            "case_count": 2,
            "passed_count": 1,
            "failed_case_count": 1,
            "pass_rate": 0.5,
            "average_precision": 0.75,
            "average_recall": 1.0,
            "average_f1": 0.8333,
        },
        "best_parameters": {
            "top_n": 2,
            "min_score": 2,
            "min_relative_score": 0.6,
        },
        "best_score": 0.8333,
        "failed_cases": [
            {
                "name": "strong_agent_title_match",
                "expected_document_ids": ["doc-agent"],
                "actual_document_ids": [
                    "doc-agent",
                    "doc-memory",
                ],
            }
        ],
    }

    text = render_scope_evaluation_report(report)

    assert "Failed cases:" in text
    assert "strong_agent_title_match" in text
    assert "doc-agent" in text
    assert "doc-memory" in text


def test_scope_evaluation_report_should_save_text_file(tmp_path):
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

    output_path = tmp_path / "scope_evaluation_report.txt"

    saved_path = save_scope_evaluation_report(
        report,
        output_path,
    )

    assert saved_path == output_path
    assert output_path.exists()

    content = output_path.read_text(
        encoding="utf-8",
    )

    assert "Knowledge Scope Evaluation Report" in content
    assert "F1: 1.0000" in content
    assert "min_relative_score: 0.6" in content


def test_scope_evaluation_report_should_create_parent_directory(tmp_path):
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

    output_path = tmp_path / "reports" / "scope" / "scope_evaluation_report.txt"

    saved_path = save_scope_evaluation_report(
        report,
        output_path,
    )

    assert saved_path == output_path
    assert output_path.exists()
    assert output_path.parent.exists()
