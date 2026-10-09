from memory.retrieval_policy import get_memory_policy
from memory.memory_score_fusion import (
    rank_memories_by_composite_score,
)
from memory.context_budget import (
    apply_memory_context_budget,
)
from memory.memory_trust_guard import (
    should_include_memory_by_trust,
)

_MEMORY_TYPES = (
    "profile",
    "skill",
    "learning",
    "project",
    "experience",
)


def _filter_trusted_memories(
    memories,
):
    return [memory for memory in memories if should_include_memory_by_trust(memory)]


def _collect_memories_blocked_by_trust(
    memory_context,
):
    blocked = {memory_type: [] for memory_type in _MEMORY_TYPES}

    for memory_type in _MEMORY_TYPES:
        for memory in memory_context.get(
            memory_type,
            [],
        ):
            if not should_include_memory_by_trust(memory):
                blocked[memory_type].append(memory)

    return blocked


def _rank_memory_type(
    memory_context,
    memory_type,
    query,
    top_k=None,
):
    trusted_memories = _filter_trusted_memories(
        memory_context.get(
            memory_type,
            [],
        )
    )

    ranked = rank_memories_by_composite_score(
        trusted_memories,
        query=query,
    )

    if top_k is None:
        return ranked

    return ranked[:top_k]


def _get_memory_type_top_k(
    memory_type,
    memory_top_k_by_type,
    learning_top_k=None,
):
    if memory_type in memory_top_k_by_type:
        return memory_top_k_by_type[memory_type]

    if memory_type == "learning":
        return learning_top_k

    return None


def _select_memory_context_before_budget(
    memory_context,
    learning_domain=None,
    query=None,
    learning_top_k=None,
    memory_top_k_by_type=None,
):
    memory_top_k_by_type = memory_top_k_by_type or {}

    selected = {memory_type: [] for memory_type in _MEMORY_TYPES}

    for memory_type in _MEMORY_TYPES:
        if memory_type == "learning":
            continue

        selected[memory_type] = _rank_memory_type(
            memory_context,
            memory_type,
            query,
            top_k=_get_memory_type_top_k(
                memory_type,
                memory_top_k_by_type,
                learning_top_k=learning_top_k,
            ),
        )

    learning_candidates = []

    trusted_learning_memories = _filter_trusted_memories(
        memory_context.get(
            "learning",
            [],
        )
    )

    for memory in trusted_learning_memories:
        memory_key = memory.get(
            "memory_key",
            "",
        )

        policy = get_memory_policy(memory_key)

        if policy.should_include(
            memory,
            learning_domain=learning_domain,
        ):
            learning_candidates.append(memory)

    ranked_learning = rank_memories_by_composite_score(
        learning_candidates,
        query=query,
    )

    learning_top_k_value = _get_memory_type_top_k(
        "learning",
        memory_top_k_by_type,
        learning_top_k=learning_top_k,
    )

    if learning_top_k_value is None:
        selected["learning"] = ranked_learning
    else:
        selected["learning"] = ranked_learning[:learning_top_k_value]

    return selected


def select_relevant_memory_context(
    memory_context,
    learning_domain=None,
    query=None,
    learning_top_k=None,
    memory_top_k_by_type=None,
    memory_budget_by_type=None,
):
    memory_budget_by_type = memory_budget_by_type or {}

    selected = _select_memory_context_before_budget(
        memory_context,
        learning_domain=learning_domain,
        query=query,
        learning_top_k=learning_top_k,
        memory_top_k_by_type=memory_top_k_by_type,
    )

    return apply_memory_context_budget(
        selected,
        memory_budget_by_type,
    )


def select_relevant_memory_context_with_budget_diagnostics(
    memory_context,
    learning_domain=None,
    query=None,
    learning_top_k=None,
    memory_top_k_by_type=None,
    memory_budget_by_type=None,
):
    memory_budget_by_type = memory_budget_by_type or {}

    blocked_by_trust = _collect_memories_blocked_by_trust(memory_context)

    before_budget = _select_memory_context_before_budget(
        memory_context,
        learning_domain=learning_domain,
        query=query,
        learning_top_k=learning_top_k,
        memory_top_k_by_type=memory_top_k_by_type,
    )

    after_budget = apply_memory_context_budget(
        before_budget,
        memory_budget_by_type,
    )

    return {
        "blocked_by_trust": blocked_by_trust,
        "before_budget": before_budget,
        "after_budget": after_budget,
    }
