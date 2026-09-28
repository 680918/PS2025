from memory.retrieval_policy import get_memory_policy


def select_relevant_memory_context(
    memory_context,
    learning_domain=None,
):
    selected = {
        "profile": list(memory_context.get("profile", [])),
        "skill": list(memory_context.get("skill", [])),
        "learning": [],
        "project": list(memory_context.get("project", [])),
        "experience": list(memory_context.get("experience", [])),
    }

    for memory in memory_context.get("learning", []):
        memory_key = memory.get("memory_key", "")

        policy = get_memory_policy(memory_key)

        if policy.should_include(
            memory,
            learning_domain=learning_domain,
        ):
            selected["learning"].append(memory)

    return selected