from planning.learning_planner import LearningPlanDecision


def build_journey_planning_decision(
    continuity,
    evaluation,
):
    if evaluation["trend"] == "insufficient_data":
        reason = "学习记录不足，继续当前主题并收集反馈。"

    elif evaluation["trend"] == "improving":
        reason = (
            "用户自评理解程度呈改善趋势，"
            "但仅凭自评变化不能确认已经掌握当前主题，"
            "继续结合具体难点安排练习。"
        )

    elif evaluation["trend"] == "declining":
        reason = (
            "用户自评理解程度呈下降趋势，"
            "不能仅凭自评分数认定实际能力退步。"
            f"上一节报告的难点：{continuity['difficulty']}。"
            f"建议下一步：{continuity['next_step']}。"
            "请优先围绕具体难点调整练习，"
            "适当减小单次任务量，并继续收集反馈。"
        )

    elif evaluation["trend"] == "stable":
        reason = (
            "用户自评理解程度变化较小，"
            "不能仅凭这一趋势认定学习停滞。"
            f"上一节报告的难点：{continuity['difficulty']}。"
            f"建议下一步：{continuity['next_step']}。"
            "请继续围绕具体难点安排练习，"
            "观察后续反馈再决定是否调整学习方法。"
        )

    else:
        reason = "继续当前主题并收集学习反馈。"

    return LearningPlanDecision(
        topic=continuity["topic"],
        action="continue",
        reason=reason,
        next_topic=None,
    )
