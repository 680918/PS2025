import json


SOURCE_LABELS = {
    "conversation": "Conversation Context",
    "learning_continuity": "Learning Continuity",
    "memory": "Memory Context",
}


def format_assembled_context(
    assembled_context,
):
    sections = []

    for source, context in assembled_context.ordered_sources():
        label = SOURCE_LABELS[source]

        formatted_context = json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
        )

        sections.append(f"{label}:\n{formatted_context}")

    return "\n\n".join(sections)


def format_assembled_context_policy(
    assembled_context,
):
    priority = " > ".join(assembled_context.source_priority)

    return f"""
Context source priority: {priority}

上下文使用规则：

1. 当前用户输入优先于所有已装配上下文。
   如果本轮用户明确提供新的状态、目标、方向或事实，
   应优先采用本轮用户输入。

2. Conversation Context：
   - 表示当前 Journey 中的最近连续对话。
   - 用于理解当前话题、指代和上下文承接。
   - 不等同于长期记忆。
   - 当前用户本轮明确提供的新信息优先于历史对话内容。

3. Learning Continuity：
   - 表示学习 Session 的连续状态。
   - 如果 has_current_session 为 true，
     current_* 字段表示当前尚未完成的学习状态，
     应优先继续当前学习主题。
   - 不得把 current session 描述为上一次学习、
     之前已经完成的学习或第一次学习。
   - 如果 has_previous_session 为 true，
     topic、understanding_score、difficulty 和 next_step
     表示 previous session 留下的历史学习状态。
   - 只有 has_current_session 和 has_previous_session
     都为 false 时，才可以把本次描述为第一次学习。
   - previous session 的 next_step 表示上一轮完成后
     留下的后续方向。
   - current_next_step 表示当前尚未完成学习的后续方向。
   - 不得把 previous session 描述为当前刚刚发生的新事实。
   - 当前用户输入中的新学习状态、目标或学习方向，
     优先于历史 Learning Continuity。

4. Memory Context：
   - 表示经过检索、筛选和预算控制后的长期记忆。
   - 只能使用记忆中明确存在的信息。
   - 不得根据记忆推测新的用户事实。
   - 如果记忆为空或信息不足，不得自行补充用户事实。
   - 当前用户本轮明确提供的新信息优先于旧记忆。
   - 不得向用户展示内部 Memory JSON
     或 Memory 系统实现细节。
"""
