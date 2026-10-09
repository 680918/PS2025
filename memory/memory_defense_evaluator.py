from memory.context_selector import (
    select_relevant_memory_context_with_budget_diagnostics,
)


_VALID_DEFENSE_OUTCOMES = {
    "blocked",
    "not_blocked",
}


def _get_memory_keys(
    memory_context,
):
    keys = []

    for memories in memory_context.values():
        for memory in memories:
            memory_key = memory.get("memory_key")

            if memory_key is not None:
                keys.append(memory_key)

    return keys


def evaluate_memory_defense_case(
    case,
):
    expected_defense = case["expected_defense"]

    if expected_defense not in (_VALID_DEFENSE_OUTCOMES):
        raise ValueError(f"invalid expected_defense: {expected_defense}")

    diagnostics = select_relevant_memory_context_with_budget_diagnostics(
        case["memory_context"],
        query=case["query"],
        learning_domain=case.get("learning_domain"),
    )

    blocked_memory_keys = _get_memory_keys(diagnostics["blocked_by_trust"])

    target_memory_key = case["target_memory_key"]

    if target_memory_key in blocked_memory_keys:
        actual_defense = "blocked"
    else:
        actual_defense = "not_blocked"

    return {
        "case_id": case["case_id"],
        "target_memory_key": (target_memory_key),
        "expected_defense": (expected_defense),
        "actual_defense": (actual_defense),
        "is_correct": (actual_defense == expected_defense),
        "blocked_memory_keys": (blocked_memory_keys),
    }
