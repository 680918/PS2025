def route_tools(user_message):

    tools = []

    learning_keywords = ["学习", "学", "成长", "提升", "进步"]

    for word in learning_keywords:
        if word in user_message:
            tools.append("get_memory_context")

            break

    if "介绍" in user_message:
        tools.append("get_user_profile")

    return tools
