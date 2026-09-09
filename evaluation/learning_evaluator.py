from dataclasses import dataclass


@dataclass
class LearningProgressResult:
    topic: str
    status: str
    previous_understanding: int | None
    current_understanding: int | None
    change: int | None
    confidence: float
    reason: str


EVIDENCE_CONFIDENCE = {
    "self_report": 0.6,
    "practice": 0.75,
    "quiz": 0.85,
    "project": 0.95,
}


def evaluate_learning_progress(topic, learning_service):
    records = learning_service.get_history(topic)

    if len(records) < 2:
        return LearningProgressResult(
            topic=topic,
            status="insufficient_data",
            previous_understanding=None,
            current_understanding=None,
            change=None,
            confidence=0.0,
            reason="At least two learning records are required.",
        )

    if len(records) >= 3:
        recent_records = records[-3:]
        previous = recent_records[0]
        current = recent_records[-1]
    else:
        previous = records[-2]
        current = records[-1]

    change = current.understanding - previous.understanding

    if change >= 5:
        status = "improving"
        reason = (
            f"Understanding increased from "
            f"{previous.understanding} to {current.understanding}."
        )

    elif change <= -5:
        status = "declining"
        reason = (
            f"Understanding decreased from "
            f"{previous.understanding} to {current.understanding}."
        )

    else:
        status = "stable"
        reason = (
            f"Understanding changed only from "
            f"{previous.understanding} to {current.understanding}."
        )

    has_evidence = bool(current.evidence.strip())

    if not has_evidence:
        confidence = 0.4
    else:
        confidence = EVIDENCE_CONFIDENCE.get(
            current.evidence_type,
            0.5,
        )

    return LearningProgressResult(
        topic=topic,
        status=status,
        previous_understanding=previous.understanding,
        current_understanding=current.understanding,
        change=change,
        confidence=confidence,
        reason=reason,
    )
