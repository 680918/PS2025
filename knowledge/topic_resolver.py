def resolve_query_topics(query):
    topics = []

    if "函数" in query:
        topics.append("函数")

    if "变量" in query:
        topics.append("变量")

    if "循环" in query:
        topics.append("循环")

    if "重复" in query and ("调用" in query or "反复" in query or "封装" in query):
        if "函数" not in topics:
            topics.append("函数")

    if "数据" in query and ("保存" in query or "放在哪里" in query or "存" in query):
        if "变量" not in topics:
            topics.append("变量")

    if (
        "连续执行" in query or "重复执行" in query or "执行很多次" in query
    ) and "循环" not in topics:
        topics.append("循环")

    return topics
