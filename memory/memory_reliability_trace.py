_MEMORY_TYPES = (
    "profile",
    "skill",
    "learning",
    "project",
    "experience",
)


def _get_memory_key(
    memory,
):
    memory_key = memory.get("memory_key")

    if memory_key is not None:
        return memory_key

    return memory.get("id")


def _summarize_memory_context(
    memory_context,
):
    count_by_type = {}
    memory_keys_by_type = {}

    total = 0

    for memory_type in _MEMORY_TYPES:
        memories = memory_context.get(
            memory_type,
            [],
        )

        count_by_type[memory_type] = len(memories)

        memory_keys_by_type[memory_type] = [
            _get_memory_key(memory) for memory in memories
        ]

        total += len(memories)

    return {
        "total": total,
        "count_by_type": (count_by_type),
        "memory_keys_by_type": (memory_keys_by_type),
    }


def _subtract_memory_context(
    source_context,
    excluded_context,
):
    result = {memory_type: [] for memory_type in _MEMORY_TYPES}

    for memory_type in _MEMORY_TYPES:
        excluded_keys = {
            _get_memory_key(memory)
            for memory in excluded_context.get(
                memory_type,
                [],
            )
        }

        for memory in source_context.get(
            memory_type,
            [],
        ):
            if _get_memory_key(memory) not in excluded_keys:
                result[memory_type].append(memory)

    return result


def _collect_removed_by_budget(
    before_budget,
    after_budget,
):
    return _subtract_memory_context(
        before_budget,
        after_budget,
    )


def build_memory_reliability_trace(
    memory_context,
    diagnostics,
):
    blocked_by_trust = diagnostics["blocked_by_trust"]

    before_budget = diagnostics["before_budget"]

    after_budget = diagnostics["after_budget"]

    trusted_candidates = _subtract_memory_context(
        memory_context,
        blocked_by_trust,
    )

    not_selected_before_budget = _subtract_memory_context(
        trusted_candidates,
        before_budget,
    )

    removed_by_budget = _collect_removed_by_budget(
        before_budget,
        after_budget,
    )

    return {
        "candidates": (_summarize_memory_context(memory_context)),
        "blocked_by_trust": (_summarize_memory_context(blocked_by_trust)),
        "trusted_candidates": (_summarize_memory_context(trusted_candidates)),
        "not_selected_before_budget": (
            _summarize_memory_context(not_selected_before_budget)
        ),
        "selected_before_budget": (_summarize_memory_context(before_budget)),
        "removed_by_budget": (_summarize_memory_context(removed_by_budget)),
        "injected": (_summarize_memory_context(after_budget)),
    }
