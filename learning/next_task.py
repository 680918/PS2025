def build_next_learning_task_context(journey, continuity):
    has_previous_learning = (
        continuity.get("has_previous_session", False)
        and continuity.get("completed") is not False
    )

    return {
        "domain": journey["domain"],
        "goal": journey["goal"],
        "has_previous_session": has_previous_learning,
        "previous_topic": (continuity.get("topic") if has_previous_learning else None),
        "understanding_score": (
            continuity.get("understanding_score") if has_previous_learning else None
        ),
        "difficulty": (continuity.get("difficulty") if has_previous_learning else None),
        "recommended_next_step": (
            continuity.get("next_step") if has_previous_learning else None
        ),
    }


def build_next_learning_task_prompt(
    context,
):
    if context["has_previous_session"] is False:
        return f"""
你是一名长期学习教练。

学习领域：
{context["domain"]}

学习目标：
{context["goal"]}

这是第一次学习。

不要虚构之前的学习记录、学习进度、难点或历史表现。

请根据学习领域和学习目标，
为用户生成第一节具体、可执行的学习任务。
"""

    return f"""
你是一名长期学习教练。

学习领域：
{context["domain"]}

学习目标：
{context["goal"]}

这是一次继续学习。

上一节主题：
{context["previous_topic"]}

理解程度：
{context["understanding_score"]}

当前难点：
{context["difficulty"]}

建议下一步：
{context["recommended_next_step"]}

请根据以上学习历史，
为用户生成下一节具体、可执行的学习任务。

优先围绕上一节的难点和建议下一步安排任务，
不要把历史学习状态描述成这一次已经完成的内容。
"""


def build_next_learning_task(
    journey,
    continuity,
):
    context = build_next_learning_task_context(
        journey=journey,
        continuity=continuity,
    )

    prompt = build_next_learning_task_prompt(context)

    return {
        "context": context,
        "prompt": prompt,
    }
