from dataclasses import dataclass


@dataclass
class SkillUpdateDecision:
    allowed: bool
    reason: str


def should_update_skill(evaluation_result):
    if evaluation_result.status == "insufficient_data":
        return SkillUpdateDecision(
            allowed=False,
            reason="Insufficient learning data.",
        )

    if evaluation_result.confidence < 0.75:
        return SkillUpdateDecision(
            allowed=False,
            reason="Evaluation confidence is too low.",
        )

    if evaluation_result.status == "stable":
        return SkillUpdateDecision(
            allowed=False,
            reason="Learning progress is stable.",
        )

    return SkillUpdateDecision(
        allowed=True,
        reason="Evaluation is strong enough to update skill state.",
    )
