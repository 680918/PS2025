def resolve_goal(memory_service):
    if memory_service is None:
        return None

    goal_memory = memory_service.get_by_key(
        "profile",
        "goal",
    )

    if goal_memory is None:
        return None

    return goal_memory.content
