# agent/context/source_selector.py


def select_context_sources(
    user_query,
):

    query = user_query.lower()

    sources = []

    learning_keywords = [
        "学习",
        "学不会",
        "掌握",
        "练习",
        "怎么提升",
        "下一步",
    ]

    memory_keywords = [
        "以前",
        "之前",
        "过去",
        "记得",
        "经历",
    ]

    for keyword in learning_keywords:
        if keyword in query:
            sources.append("learning")
            break

    for keyword in memory_keywords:
        if keyword in query:
            sources.append("memory")
            break

    general_keywords = [
        "什么是",
        "是什么",
        "解释",
        "介绍",
    ]

    for keyword in general_keywords:
        if keyword in query:
            sources.append("knowledge")
            break

    personal_knowledge_keywords = [
        "之前整理",
        "以前整理",
        "我整理",
        "我的教程",
        "我的笔记",
        "我的总结",
        "之前总结",
        "以前总结",
    ]

    for keyword in personal_knowledge_keywords:
        if keyword in query:
            if "knowledge" not in sources:
                sources.append("knowledge")
            break

    learning_reflection_keywords = [
        "为什么学不会",
        "总是不会",
        "哪里不足",
        "我的问题",
        "怎么改进",
    ]

    for keyword in learning_reflection_keywords:
        if keyword in query:
            if "learning" not in sources:
                sources.append("learning")

            if "memory" not in sources:
                sources.append("memory")

            break

    return sources
