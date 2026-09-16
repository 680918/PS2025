import pytest

from knowledge.scope_evaluation_comparison import (
    compare_scope_evaluation_reports,
    render_scope_evaluation_comparison,
    save_scope_evaluation_comparison,
)


def test_scope_evaluation_comparison_should_calculate_metric_deltas():
    previous_report = {
        "summary": {
            "pass_rate": 0.8,
            "average_precision": 0.9,
            "average_recall": 0.8,
            "average_f1": 0.85,
        }
    }

    current_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 0.95,
            "average_recall": 0.9,
            "average_f1": 0.92,
        }
    }

    result = compare_scope_evaluation_reports(
        previous_report=previous_report,
        current_report=current_report,
    )

    assert result["pass_rate_delta"] == pytest.approx(0.2)
    assert result["precision_delta"] == pytest.approx(0.05)
    assert result["recall_delta"] == pytest.approx(0.1)
    assert result["f1_delta"] == pytest.approx(0.07)


def test_scope_evaluation_comparison_should_report_negative_deltas():
    previous_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        }
    }

    current_report = {
        "summary": {
            "pass_rate": 0.8,
            "average_precision": 0.9,
            "average_recall": 0.85,
            "average_f1": 0.87,
        }
    }

    result = compare_scope_evaluation_reports(
        previous_report=previous_report,
        current_report=current_report,
    )

    assert result["pass_rate_delta"] == pytest.approx(-0.2)
    assert result["precision_delta"] == pytest.approx(-0.1)
    assert result["recall_delta"] == pytest.approx(-0.15)
    assert result["f1_delta"] == pytest.approx(-0.13)


def test_scope_evaluation_comparison_should_classify_improvement():
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
            "pass_rate": 0.9,
            "average_precision": 0.9,
            "average_recall": 0.9,
            "average_f1": 0.9,
        }
    }

    result = compare_scope_evaluation_reports(
        previous_report=previous_report,
        current_report=current_report,
    )

    assert result["status"] == "improved"


def test_scope_evaluation_comparison_should_classify_regression():
    previous_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        }
    }

    current_report = {
        "summary": {
            "pass_rate": 0.9,
            "average_precision": 0.9,
            "average_recall": 0.9,
            "average_f1": 0.9,
        }
    }

    result = compare_scope_evaluation_reports(
        previous_report=previous_report,
        current_report=current_report,
    )

    assert result["status"] == "regressed"


def test_scope_evaluation_comparison_should_classify_unchanged():
    report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        }
    }

    result = compare_scope_evaluation_reports(
        previous_report=report,
        current_report=report,
    )

    assert result["status"] == "unchanged"


def test_scope_evaluation_comparison_should_treat_tiny_f1_delta_as_unchanged():
    previous_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0,
        }
    }

    current_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 1.0 + 1e-12,
        }
    }

    result = compare_scope_evaluation_reports(
        previous_report=previous_report,
        current_report=current_report,
    )

    assert result["status"] == "unchanged"


def test_scope_evaluation_comparison_should_classify_change_above_tolerance():
    previous_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 0.9,
        }
    }

    current_report = {
        "summary": {
            "pass_rate": 1.0,
            "average_precision": 1.0,
            "average_recall": 1.0,
            "average_f1": 0.91,
        }
    }

    result = compare_scope_evaluation_reports(
        previous_report=previous_report,
        current_report=current_report,
    )

    assert result["status"] == "improved"


def test_scope_evaluation_comparison_should_render_readable_text():
    comparison = {
        "pass_rate_delta": 0.1,
        "precision_delta": 0.05,
        "recall_delta": -0.02,
        "f1_delta": 0.03,
        "status": "improved",
    }

    text = render_scope_evaluation_comparison(
        comparison,
    )

    assert "Knowledge Scope Regression Comparison" in text
    assert "Status: improved" in text
    assert "Pass rate delta: +0.1000" in text
    assert "Precision delta: +0.0500" in text
    assert "Recall delta: -0.0200" in text
    assert "F1 delta: +0.0300" in text


def test_scope_evaluation_comparison_should_save_text_file(tmp_path):
    comparison = {
        "pass_rate_delta": 0.1,
        "precision_delta": 0.05,
        "recall_delta": -0.02,
        "f1_delta": 0.03,
        "status": "improved",
    }

    output_path = tmp_path / "reports" / "scope_regression_comparison.txt"

    saved_path = save_scope_evaluation_comparison(
        comparison,
        output_path,
    )

    assert saved_path == output_path
    assert output_path.exists()

    content = output_path.read_text(
        encoding="utf-8",
    )

    assert "Knowledge Scope Regression Comparison" in content
    assert "Status: improved" in content
    assert "F1 delta: +0.0300" in content
