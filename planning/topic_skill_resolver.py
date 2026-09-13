TOPIC_SKILL_MAP = {
    "Python变量": "Python",
    "Python条件判断": "Python",
    "Python循环": "Python",
    "Python函数": "Python",
    "Python异常处理": "Python",
    "Python文件操作": "Python",
    "Python模块": "Python",
    "Python面向对象基础": "Python",
}


def resolve_skill_from_topic(topic):
    return TOPIC_SKILL_MAP.get(topic)
