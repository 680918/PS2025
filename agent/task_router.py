def route_task(user_message):

    planning_keywords = ["学习路线", "学习规划", "学习计划", "三个月", "长期规划"]

    for word in planning_keywords:
        if word in user_message:
            return "planning"

    return "simple"
