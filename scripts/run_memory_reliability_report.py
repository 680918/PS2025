import argparse

from memory.memory_reliability_report_service import (
    build_memory_reliability_report,
)
from memory.memory_reliability_run_record_runtime import (
    open_user_memory_reliability_run_record_store,
)
from memory.memory_reliability_trend import (
    compare_memory_reliability_trends,
)
from memory.memory_reliability_trend_interpretation import (
    interpret_memory_reliability_trend,
)


def _build_parser():
    parser = argparse.ArgumentParser(
        description=("Show Memory reliability metrics for one user.")
    )

    parser.add_argument(
        "--database-dir",
        required=True,
    )

    parser.add_argument(
        "--user-id",
        required=True,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--trend-window",
        type=int,
        default=None,
    )

    return parser


def format_memory_reliability_report(
    report,
):
    averages = report["averages"]
    rates = report["rates"]

    lines = [
        "=" * 64,
        "Memory Reliability Report",
        "=" * 64,
        "",
        f"Runs: {report['run_count']}",
        "",
        (f"Average candidates/run: {averages['candidates_per_run']:.2f}"),
        (f"Average injected/run:   {averages['injected_per_run']:.2f}"),
        "",
        (f"Trust block rate:       {rates['trust_block_rate']:.2%}"),
        (f"Selection drop rate:   {rates['selection_drop_rate']:.2%}"),
        (f"Budget drop rate:       {rates['budget_drop_rate']:.2%}"),
        (f"Injection rate:        {rates['injection_rate']:.2%}"),
    ]

    return "\n".join(lines)


def format_memory_reliability_trend(
    interpretation,
):
    lines = [
        "=" * 64,
        "Memory Reliability Trend",
        "=" * 64,
        "",
        (f"Window size: {interpretation['window_size']}"),
        "",
        "Rate changes:",
    ]

    for fact in interpretation["facts"]:
        if not fact["comparable"]:
            lines.append((f"  {fact['metric']}: not comparable (zero denominator)"))
            continue

        lines.append(
            (
                f"  {fact['metric']}: "
                f"{fact['previous']:.2%} "
                "-> "
                f"{fact['recent']:.2%} "
                f"({fact['delta']:+.2%})"
            )
        )

    lines.extend(
        [
            "",
            "Investigation signals:",
        ]
    )

    if interpretation["signals"]:
        for signal in interpretation["signals"]:
            lines.append(
                (f"  {signal['signal']} ({signal['metric']}, {signal['direction']})")
            )
    else:
        lines.append("  none")

    return "\n".join(lines)


def main(
    argv=None,
):
    args = _build_parser().parse_args(argv)

    store = open_user_memory_reliability_run_record_store(
        database_dir=args.database_dir,
        user_id=args.user_id,
    )

    report = build_memory_reliability_report(
        store=store,
        limit=args.limit,
    )

    print(format_memory_reliability_report(report))

    if args.trend_window is not None:
        trend = compare_memory_reliability_trends(
            store=store,
            window_size=(args.trend_window),
        )

        interpretation = interpret_memory_reliability_trend(trend)

        print()

        print(format_memory_reliability_trend(interpretation))


if __name__ == "__main__":
    main()
