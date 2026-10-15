from dataclasses import dataclass
from agent.evaluation_models import (
    EvaluationResult,
)


@dataclass
class ContextEvaluationResult:
    success: bool

    expected_source: str

    actual_source: str

    policy: str


def evaluate_policy_compliance(
    resolution_trace,
):
    results = {}

    for field_name, trace in resolution_trace.items():
        priority = trace.get(
            "priority",
            [],
        )

        winner = trace.get(
            "winner",
        )

        if not priority:
            results[field_name] = {
                "passed": False,
                "reason": "missing priority",
            }
            continue

        expected_winner = priority[0]

        results[field_name] = EvaluationResult(
            metric="policy_compliance",
            passed=winner == expected_winner,
            details={
                "expected": expected_winner,
                "actual": winner,
            },
        )

    return results


def evaluate_trace_completeness(
    resolution_trace,
):
    results = {}

    required_fields = [
        "winner",
        "value",
        "policy_name",
        "priority",
    ]

    for field_name, trace in resolution_trace.items():
        missing = [field for field in required_fields if field not in trace]

        results[field_name] = EvaluationResult(
            metric="trace_completeness",
            passed=len(missing) == 0,
            details={
                "missing": missing,
            },
        )

    return results


def evaluate_conflict_detection(
    expected_conflicts,
    actual_conflicts,
):
    results = {}

    for field_name in expected_conflicts:
        detected = field_name in actual_conflicts

        results[field_name] = EvaluationResult(
            metric="conflict_detection",
            passed=detected,
            details={
                "detected": detected,
            },
        )

    return results
