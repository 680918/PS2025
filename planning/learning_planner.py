from dataclasses import dataclass
from planning.learning_path import get_next_topic
from planning.goal_skill_path import get_next_skill
from planning.topic_skill_resolver import resolve_skill_from_topic
from planning.goal_resolver import resolve_goal


@dataclass
class LearningPlanDecision:
    topic: str
    action: str
    reason: str
    next_topic: str | None = None


def decide_learning_action(
    topic,
    understanding,
    status,
    confidence,
):
    if status == "improving" and understanding >= 85 and confidence >= 0.75:
        return LearningPlanDecision(
            topic=topic,
            action="advance",
            reason=(
                "Learning progress is improving, "
                "understanding is high, "
                "and evaluation confidence is sufficient."
            ),
        )

    if status == "stable" and understanding >= 90 and confidence >= 0.75:
        return LearningPlanDecision(
            topic=topic,
            action="advance",
            reason=(
                "Understanding is very high and evaluation confidence "
                "is sufficient, so the learner is ready to advance "
                "even though recent progress is stable."
            ),
        )

    if status == "stable" and understanding >= 80 and confidence >= 0.75:
        return LearningPlanDecision(
            topic=topic,
            action="review",
            reason=(
                "Understanding is high but not yet at the mastery threshold, "
                "so review is appropriate before advancing."
            ),
        )

    if status == "declining" and confidence >= 0.75:
        return LearningPlanDecision(
            topic=topic,
            action="remediate",
            reason=(
                "Learning performance is declining, "
                "so the current topic should be reinforced "
                "before moving forward."
            ),
        )

    return LearningPlanDecision(
        topic=topic,
        action="continue",
        reason="Continue learning the current topic.",
    )


def build_next_learning_decision(
    topic,
    understanding,
    status,
    confidence,
    goal=None,
    current_skill=None,
    memory_service=None,
):
    if current_skill is None:
        current_skill = resolve_skill_from_topic(topic)

    if goal is None:
        goal = resolve_goal(memory_service)

    decision = decide_learning_action(
        topic=topic,
        understanding=understanding,
        status=status,
        confidence=confidence,
    )

    next_topic = None

    if decision.action == "advance":
        next_topic = get_next_topic(topic)

        if next_topic is None:
            if goal is not None and current_skill is not None:
                next_skill = get_next_skill(
                    goal=goal,
                    current_skill=current_skill,
                )

                if next_skill is not None:
                    return LearningPlanDecision(
                        topic=decision.topic,
                        action="advance",
                        reason=(
                            "The current learning path is complete, "
                            "so advance to the next skill in the goal path."
                        ),
                        next_topic=next_skill,
                    )

            return LearningPlanDecision(
                topic=decision.topic,
                action="review",
                reason=(
                    "The current topic is at the end of the learning path, "
                    "and no next skill is available."
                ),
                next_topic=None,
            )

    return LearningPlanDecision(
        topic=decision.topic,
        action=decision.action,
        reason=decision.reason,
        next_topic=next_topic,
    )


def build_next_learning_decision_from_evaluation(
    evaluation_result,
    memory_service=None,
):
    return build_next_learning_decision(
        topic=evaluation_result.topic,
        understanding=evaluation_result.current_understanding,
        status=evaluation_result.status,
        confidence=evaluation_result.confidence,
        memory_service=memory_service,
    )
