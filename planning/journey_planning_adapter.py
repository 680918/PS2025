from planning.learning_planner import LearningPlanDecision
from planning.learning_path import get_next_topic


action = "continue"


def build_journey_planning_decision(
    continuity,
    evaluation,
    evidence_summary=None,
    previous_session_evidence_summary=None,
):

    action = "continue"

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

    if previous_session_evidence_summary is not None:
        previous_quality = previous_session_evidence_summary.get(
            "quality_summary",
            {},
        )

        previous_evidence_count = previous_session_evidence_summary.get(
            "evidence_count",
            0,
        )

        all_previous_evidence_strong = (
            previous_evidence_count > 0
            and previous_quality.get("strong", 0) == previous_evidence_count
            and previous_quality.get("weak", 0) == 0
            and previous_quality.get("insufficient", 0) == 0
        )

        all_previous_evidence_weak = (
            previous_evidence_count > 0
            and previous_quality.get("strong", 0) == 0
            and previous_quality.get("weak", 0) == previous_evidence_count
            and previous_quality.get("insufficient", 0) == 0
        )

        if evaluation["trend"] == "improving" and all_previous_evidence_strong:
            action = "advance"
            reason += " 上一节学习证据充分且学习趋势改善，支持进入下一阶段学习。"

        elif all_previous_evidence_weak:
            action = "review"
            reason += (
                " 上一节学习主要依赖较弱证据，"
                "请增加拓展练习，并通过新的练习结果验证掌握程度。"
            )

        elif previous_quality.get("insufficient", 0) > 0:
            action = "remediate"
            reason += (
                " 上一节学习存在证据不足的练习，"
                "请针对未充分掌握的内容进行补强练习，"
                "并通过新的测试结果再次验证掌握程度。"
            )

    if evidence_summary is not None:
        evidence_count = evidence_summary["evidence_count"]
        completed_tasks = evidence_summary["completed_tasks"]

        if evidence_count > 0 and completed_tasks < evidence_count:
            reason += (
                f" 已记录练习完成情况：{completed_tasks}/{evidence_count}。"
                "请继续围绕未完成练习安排任务。"
            )

        elif evidence_count > 0 and completed_tasks == evidence_count:
            reason += (
                f" 已记录练习完成情况：{completed_tasks}/{evidence_count}。"
                "本组练习记录已全部完成，"
                "但不能仅凭这一结果确认已掌握整个主题，"
                "请继续结合具体难点安排学习任务。"
            )

    next_topic = None

    if action == "advance":
        next_topic = get_next_topic(continuity["topic"])

    return LearningPlanDecision(
        topic=continuity["topic"],
        action=action,
        reason=reason,
        next_topic=next_topic,
    )
