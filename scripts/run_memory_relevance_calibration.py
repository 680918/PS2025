from memory.relevance_calibration_runner import (
    run_relevance_calibration,
    run_relevance_calibration_regression,
)


def format_calibration_report(report):
    lines = []

    lines.append("Memory Relevance Calibration")

    lines.append("")

    for case in report.get(
        "cases",
        [],
    ):
        lines.append(f"Case: {case['name']}")

        lines.append(f"Accuracy: {case['pairwise_order_accuracy']:.2f}")

        lines.append(
            f"Minimum Pairwise Margin: {case.get('minimum_pairwise_margin', 0.0):.2f}"
        )

        for item in case.get(
            "scored_items",
            [],
        ):
            lines.append(
                f"{item['memory_key']} "
                f"relevance={item['relevance']} "
                f"score={item['score']:.2f}"
            )

        for violation in case.get(
            "pairwise_violations",
            [],
        ):
            lines.append("Violation:")

            lines.append(
                f"{violation['higher_relevance_key']} "
                f"relevance={violation['higher_relevance']} "
                f"score={violation['higher_score']:.2f}"
            )

            lines.append("should rank above")

            lines.append(
                f"{violation['lower_relevance_key']} "
                f"relevance={violation['lower_relevance']} "
                f"score={violation['lower_score']:.2f}"
            )

        lines.append("")

    lines.append("Average Pairwise Order Accuracy")

    lines.append(f"{report['average_pairwise_order_accuracy']:.2f}")

    lines.append("")

    lines.append(
        "Minimum Pairwise Margin Across Cases: "
        f"{report.get('minimum_pairwise_margin', 0.0):.2f}"
    )

    lines.append(
        "Average Minimum Pairwise Margin: "
        f"{report.get('average_minimum_pairwise_margin', 0.0):.2f}"
    )

    weakest_pair = report.get("weakest_pair")

    if weakest_pair is not None:
        lines.append("")
        lines.append("Global Weakest Pair")

        lines.append(f"Case: {weakest_pair['case_name']}")

        lines.append(
            f"{weakest_pair['higher_relevance_key']} "
            f"relevance={weakest_pair['higher_relevance']} "
            f"score={weakest_pair['higher_score']:.2f}"
        )

        lines.append("vs")

        lines.append(
            f"{weakest_pair['lower_relevance_key']} "
            f"relevance={weakest_pair['lower_relevance']} "
            f"score={weakest_pair['lower_score']:.2f}"
        )

        lines.append(f"Margin: {weakest_pair['margin']:.2f}")

    return "\n".join(lines)


def format_regression_report(report):
    lines = []

    lines.append("Calibration Regression")

    status = "PASS" if report.get("passed") else "FAIL"

    lines.append("")
    lines.append(f"Status: {status}")

    regressions = report.get(
        "regressions",
        [],
    )

    if regressions:
        lines.append("")
        lines.append("Regression Metrics:")

        baseline = report.get(
            "baseline",
            {},
        )

        current = report.get(
            "current",
            {},
        )

        deltas = report.get(
            "deltas",
            {},
        )

        for metric in regressions:
            lines.append("")

            lines.append(metric)

            lines.append(f"Baseline: {baseline.get(metric, 0.0):.2f}")

            lines.append(f"Current:  {current.get(metric, 0.0):.2f}")

            lines.append(f"Delta:    {deltas.get(metric, 0.0):.2f}")

    return "\n".join(lines)


def build_calibration_output():
    calibration_report = run_relevance_calibration()

    regression_report = run_relevance_calibration_regression(calibration_report)

    calibration_output = format_calibration_report(calibration_report)

    regression_output = format_regression_report(regression_report)

    return calibration_output + "\n\n" + regression_output


def main():
    output = build_calibration_output()

    print(output)


if __name__ == "__main__":
    main()
