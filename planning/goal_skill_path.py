from planning.goal_type_resolver import resolve_goal_type

GOAL_SKILL_PATHS = {
    "AI Agent": [
        "Python",
        "Tool Calling",
        "Memory",
        "Planning",
        "Evaluation",
        "Agent Architecture",
    ]
}


def get_skill_path(goal):
    goal_type = resolve_goal_type(goal)

    if goal_type is None:
        return []

    return GOAL_SKILL_PATHS.get(goal_type, [])


def get_next_skill(goal, current_skill):
    skill_path = get_skill_path(goal)

    if current_skill not in skill_path:
        return None

    current_index = skill_path.index(current_skill)

    if current_index == len(skill_path) - 1:
        return None

    return skill_path[current_index + 1]
