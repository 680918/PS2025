from memory.memory_pairwise_calibration import (
    run_memory_pairwise_calibration,
)


def summarize_pairwise_stability(
    reports,
):
    if not reports:
        return {
            "runs": 0,
            "run_accuracies": [],
            "mean_accuracy": 0.0,
            "min_accuracy": 0.0,
            "max_accuracy": 0.0,
            "total_cases": 0,
            "stable_correct_cases": 0,
            "unstable_case_count": 0,
            "unstable_cases": [],
            "case_results": [],
            "consensus_correct_cases": 0,
            "consensus_accuracy": 0.0,
        }

    run_accuracies = [report["summary"]["accuracy"] for report in reports]

    cases = {}

    for report in reports:
        for result in report["results"]:
            case_id = result["case_id"]

            entry = cases.setdefault(
                case_id,
                {
                    "case_id": case_id,
                    "category": result["category"],
                    "expected_effect": result["expected_effect"],
                    "observed_effects": [],
                },
            )

            entry["observed_effects"].append(result["pairwise_actual_effect"])

    case_results = []

    for entry in cases.values():
        expected_effect = entry["expected_effect"]

        observed_effects = entry["observed_effects"]

        correct_count = sum(
            1 for effect in observed_effects if effect == expected_effect
        )

        gold_accuracy = correct_count / len(observed_effects)

        effect_consistent = len(set(observed_effects)) == 1

        is_stable_correct = gold_accuracy == 1.0 and effect_consistent

        consensus_effect, consensus_rate = _calculate_consensus(observed_effects)

        consensus_correct = consensus_effect == expected_effect

        case_results.append(
            {
                **entry,
                "gold_accuracy": (gold_accuracy),
                "effect_consistent": (effect_consistent),
                "is_stable_correct": (is_stable_correct),
                "consensus_effect": (consensus_effect),
                "consensus_rate": (consensus_rate),
                "consensus_correct": (consensus_correct),
            }
        )

    unstable_cases = [case for case in case_results if not case["is_stable_correct"]]

    stable_correct_cases = sum(1 for case in case_results if case["is_stable_correct"])

    consensus_correct_cases = sum(
        1 for case in case_results if case["consensus_correct"]
    )

    consensus_accuracy = (
        consensus_correct_cases / len(case_results) if case_results else 0.0
    )

    return {
        "runs": len(reports),
        "run_accuracies": (run_accuracies),
        "mean_accuracy": (sum(run_accuracies) / len(run_accuracies)),
        "min_accuracy": min(run_accuracies),
        "max_accuracy": max(run_accuracies),
        "total_cases": len(case_results),
        "stable_correct_cases": (stable_correct_cases),
        "unstable_case_count": len(unstable_cases),
        "unstable_cases": (unstable_cases),
        "case_results": (case_results),
        "consensus_correct_cases": (consensus_correct_cases),
        "consensus_accuracy": (consensus_accuracy),
    }


def run_memory_pairwise_stability(
    llm_call,
    runs=3,
    cases=None,
):
    if runs < 1:
        raise ValueError("runs must be at least 1")

    reports = []

    for _ in range(runs):
        report = run_memory_pairwise_calibration(
            llm_call=llm_call,
            cases=cases,
        )

        reports.append(report)

    return summarize_pairwise_stability(reports)


def _calculate_consensus(
    observed_effects,
):
    counts = {}

    for effect in observed_effects:
        counts[effect] = (
            counts.get(
                effect,
                0,
            )
            + 1
        )

    highest_count = max(counts.values())

    winners = [effect for effect, count in counts.items() if count == highest_count]

    consensus_rate = highest_count / len(observed_effects)

    if len(winners) != 1:
        return None, consensus_rate

    return (
        winners[0],
        consensus_rate,
    )
