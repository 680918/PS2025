from memory.relevance_ranker import rank_memories
from memory.retrieval_policy import get_memory_policy

_MEMORY_TYPES = (
    "profile",
    "skill",
    "learning",
    "project",
    "experience",
)


def _rank_memory_type(
    memory_context,
    memory_type,
    query,
    top_k=None,
):
    return rank_memories(
        memory_context.get(memory_type, []),
        query=query,
        top_k=top_k,
    )


def select_relevant_memory_context(
    memory_context,
    learning_domain=None,
    query=None,
    learning_top_k=None,
    memory_top_k_by_type=None,
):
    selected = {memory_type: [] for memory_type in _MEMORY_TYPES}

    memory_top_k_by_type = memory_top_k_by_type or {}

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

    for memory in memory_context.get("learning", []):
        memory_key = memory.get("memory_key", "")

        policy = get_memory_policy(memory_key)

        if policy.should_include(
            memory,
            learning_domain=learning_domain,
        ):
            learning_candidates.append(memory)

    selected["learning"] = rank_memories(
        learning_candidates,
        query=query,
        top_k=_get_memory_type_top_k(
            "learning",
            memory_top_k_by_type,
            learning_top_k=learning_top_k,
        ),
    )

    return selected


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
