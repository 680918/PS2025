KNOWLEDGE_CREATION_KEYWORDS = [
    "整理",
    "总结",
    "教程",
    "笔记",
    "保存",
    "沉淀",
    "归档",
]


def is_knowledge_creation_request(
    user_message,
):

    if not user_message:
        return False

    message = user_message.lower()

    return any(keyword in message for keyword in KNOWLEDGE_CREATION_KEYWORDS)
