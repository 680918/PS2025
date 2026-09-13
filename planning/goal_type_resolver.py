def resolve_goal_type(goal):
    if not goal:
        return None

    normalized = goal.strip()

    if normalized == "AI Agent":
        return "AI Agent"

    if "AI Agent" in normalized:
        return "AI Agent"

    return None
