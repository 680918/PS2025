def resolve_skill_key(topic, memory_service):
    skills = memory_service.store.list_by_type("skill")

    skill_keys = [skill.memory_key for skill in skills if skill.memory_key]

    # 1. 完全匹配
    if topic in skill_keys:
        return topic

    # 2. 父级技能名称包含在学习主题中
    matches = [skill_key for skill_key in skill_keys if skill_key in topic]

    if not matches:
        return None

    # 优先最长匹配，避免未来出现：
    # "Python" 和 "Python函数" 同时存在时选错
    return max(matches, key=len)
