def build_next_learning_task_context(
    journey,
    continuity,
    evaluation=None,
):
    has_previous_learning = (
        continuity.get("has_previous_session", False)
        and continuity.get("completed") is not False
    )

    return {
        "domain": journey["domain"],
        "goal": journey["goal"],
        "has_previous_session": has_previous_learning,

        "previous_topic": (
            continuity.get("topic")
            if has_previous_learning
            else None
        ),

        "understanding_score": (
            continuity.get("understanding_score")
            if has_previous_learning
            else None
        ),

        "difficulty": (
            continuity.get("difficulty")
            if has_previous_learning
            else None
        ),

        "recommended_next_step": (
            continuity.get("next_step")
            if has_previous_learning
            else None
        ),

        "evaluation": evaluation,
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

    evaluation_text = ""

    evaluation = context.get("evaluation")

    if evaluation:
        evaluation_text = f"""
长期学习趋势：

已完成学习：{evaluation.get("completed_sessions")}

首次理解程度：{evaluation.get("first_understanding")}

最新理解程度：{evaluation.get("latest_understanding")}

理解程度变化：{evaluation.get("understanding_change")}

趋势：{evaluation.get("trend")}

以上理解程度为用户自评数据，
请结合趋势辅助制定下一节学习任务。
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

{evaluation_text}

请根据以上学习历史，
为用户生成下一节具体、可执行的学习任务。

优先围绕上一节的难点和建议下一步安排任务，
不要把历史学习状态描述成这一次已经完成的内容。
"""

def build_next_learning_task(
    journey,
    continuity,
    evaluation=None
):
    context = build_next_learning_task_context(
        journey=journey,
        continuity=continuity,
        evaluation=evaluation,
    )

    prompt = build_next_learning_task_prompt(context)

    return {
        "context": context,
        "prompt": prompt,
    }
