from dataclasses import dataclass, field


@dataclass
class CoachResponseContract:
    facts: list[str] = field(default_factory=list)
    assessment: dict | None = None
    recommendation: dict | None = None


def build_coach_response_contract(
    learning_record,
    evaluation,
    planning_decision,
):
    facts = [
        f"理解度自评{learning_record.understanding}%",
    ]

    if learning_record.evidence:
        facts.append(learning_record.evidence)

    assessment = {
        "status": evaluation.status,
        "confidence": evaluation.confidence,
        "current_understanding": evaluation.current_understanding,
    }

    recommendation = {
        "action": planning_decision.action,
        "next_topic": planning_decision.next_topic,
        "reason": planning_decision.reason,
    }

    return CoachResponseContract(
        facts=facts,
        assessment=assessment,
        recommendation=recommendation,
    )
