def route_tools(user_message):

    tools = []

    learning_keywords = ["学习", "学", "成长", "提升", "进步"]

    for word in learning_keywords:
        if word in user_message:
            tools.append("get_memory_context")
            break

    feedback_keywords = [
        "理解",
        "掌握",
        "完成",
        "练习",
        "测验",
        "测试",
        "考试",
        "项目",
    ]

    has_learning_context = any(word in user_message for word in learning_keywords)

    has_feedback_signal = any(word in user_message for word in feedback_keywords)

    if has_learning_context and has_feedback_signal:
        tools.append("save_learning_feedback")

    if "介绍" in user_message:
        tools.append("get_user_profile")

    return tools
