from scripts.run_memory_relevance_calibration import (
    build_calibration_output,
)


def test_build_calibration_output_should_return_report_text():

    output = build_calibration_output()

    assert isinstance(
        output,
        str,
    )

    assert "Memory Relevance Calibration" in output

    assert "Average Pairwise Order Accuracy" in output
