def limit_memory_context_by_budget(
    memories,
    max_characters,
):
    selected = []
    used_characters = 0

    for memory in memories:
        content = memory.get(
            "content",
            "",
        )

        content_length = len(content)

        # 单条本身永远无法进入预算
        if content_length > max_characters:
            continue

        # 当前排序靠前的 memory 放不下
        # 后面的 memory 不能越过它
        if used_characters + content_length > max_characters:
            break

        selected.append(memory)
        used_characters += content_length

    return selected


def calculate_memory_context_usage(
    memory_context,
):
    usage_by_type = {}
    count_by_type = {}

    total_characters = 0
    total_memories = 0

    for memory_type, memories in memory_context.items():
        type_characters = sum(len(memory.get("content", "")) for memory in memories)

        type_count = len(memories)

        usage_by_type[memory_type] = type_characters
        count_by_type[memory_type] = type_count

        total_characters += type_characters
        total_memories += type_count

    return {
        "by_type": usage_by_type,
        "count_by_type": count_by_type,
        "total_characters": total_characters,
        "total_memories": total_memories,
    }


def calculate_memory_context_budget_impact(
    before_usage,
    after_usage,
):
    before_characters = before_usage["total_characters"]
    after_characters = after_usage["total_characters"]

    reduced_characters = before_characters - after_characters

    if before_characters == 0:
        reduction_ratio = 0.0
    else:
        reduction_ratio = reduced_characters / before_characters

    return {
        "before_characters": before_characters,
        "after_characters": after_characters,
        "reduced_characters": reduced_characters,
        "reduction_ratio": reduction_ratio,
    }


def apply_memory_context_budget(
    memory_context,
    memory_budget_by_type,
):
    limited_context = {}

    for memory_type, memories in memory_context.items():
        memory_budget = memory_budget_by_type.get(
            memory_type,
        )

        if memory_budget is None:
            limited_context[memory_type] = list(memories)
            continue

        limited_context[memory_type] = limit_memory_context_by_budget(
            memories,
            max_characters=memory_budget,
        )

    return limited_context
