from scripts.run_memory_relevance_calibration import (
    build_calibration_output,
    format_calibration_report,
)


def test_build_calibration_output_should_return_report_text():

    output = build_calibration_output()

    assert isinstance(
        output,
        str,
    )

    assert "Memory Relevance Calibration" in output

    assert "Average Pairwise Order Accuracy" in output


def test_calibration_output_should_include_scored_items():
    output = build_calibration_output()

    assert "learning_feedback:python-tool-calling" in output
    assert "relevance=" in output
    assert "score=" in output


def test_calibration_output_should_include_pairwise_violations():
    report = {
        "cases": [
            {
                "name": "failing_case",
                "pairwise_order_accuracy": 0.67,
                "scored_items": [],
                "pairwise_violations": [
                    {
                        "higher_relevance_key": "learning_feedback:partial",
                        "higher_relevance": 1,
                        "higher_score": 0.0,
                        "lower_relevance_key": "learning_feedback:irrelevant",
                        "lower_relevance": 0,
                        "lower_score": 0.0,
                    }
                ],
            }
        ],
        "average_pairwise_order_accuracy": 0.67,
    }

    output = format_calibration_report(report)

    assert "Violation:" in output
    assert "learning_feedback:partial" in output
    assert "should rank above" in output
    assert "learning_feedback:irrelevant" in output


def test_calibration_output_should_include_minimum_pairwise_margin():
    output = build_calibration_output()

    assert "Minimum Pairwise Margin:" in output


def test_calibration_output_should_include_dataset_margin_summary():
    output = build_calibration_output()

    assert "Minimum Pairwise Margin Across Cases:" in output
    assert "Average Minimum Pairwise Margin:" in output


def test_calibration_output_should_include_global_weakest_pair():
    report = {
        "cases": [],
        "average_pairwise_order_accuracy": 1.0,
        "minimum_pairwise_margin": 0.12,
        "average_minimum_pairwise_margin": 0.41,
        "weakest_pair": {
            "case_name": "agent_memory",
            "higher_relevance_key": "learning_feedback:memory-retrieval",
            "higher_relevance": 1,
            "higher_score": 0.12,
            "lower_relevance_key": "learning_feedback:english",
            "lower_relevance": 0,
            "lower_score": 0.0,
            "margin": 0.12,
        },
    }

    output = format_calibration_report(report)

    assert "Global Weakest Pair" in output
    assert "Case: agent_memory" in output
    assert "learning_feedback:memory-retrieval" in output
    assert "learning_feedback:english" in output
    assert "Margin: 0.12" in output
