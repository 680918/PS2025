from memory.relevance_calibration_runner import (
    run_relevance_calibration,
)


def format_calibration_report(
    report,
):
    lines = []

    lines.append("Memory Relevance Calibration")

    lines.append("")

    for case in report.get(
        "cases",
        [],
    ):
        lines.append(f"Case: {case['name']}")

        lines.append(f"Accuracy: {case['pairwise_order_accuracy']:.2f}")

        lines.append("")

    lines.append("Average Pairwise Order Accuracy")

    lines.append(f"{report['average_pairwise_order_accuracy']:.2f}")

    return "\n".join(lines)


def build_calibration_output():

    report = run_relevance_calibration()

    return format_calibration_report(
        report,
    )


def main():

    output = build_calibration_output()

    print(output)


if __name__ == "__main__":
    main()
