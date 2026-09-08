from dataclasses import dataclass


@dataclass
class MemoryDecision:
    allowed: bool
    reason: str


SOURCE_RELIABILITY = {
    "single_observation": 0.4,
    "agent_inference": 0.6,
    "learning_feedback": 0.8,
    "user_confirmed": 1.0,
}


class MemoryPolicy:
    def evaluate(
        self,
        existing,
        new_confidence,
        new_importance,
        new_source,
        new_updated_at,
    ):
        if new_confidence > existing.confidence:
            return MemoryDecision(
                allowed=True,
                reason="new_confidence_higher",
            )

        if new_confidence < existing.confidence:
            return MemoryDecision(
                allowed=False,
                reason="new_confidence_lower",
            )

        if new_importance > existing.importance:
            return MemoryDecision(
                allowed=True,
                reason="new_importance_higher",
            )

        if new_importance < existing.importance:
            return MemoryDecision(
                allowed=False,
                reason="new_importance_lower",
            )

        old_source_score = SOURCE_RELIABILITY.get(
            existing.source,
            0.5,
        )

        new_source_score = SOURCE_RELIABILITY.get(
            new_source,
            0.5,
        )

        if new_source_score > old_source_score:
            return MemoryDecision(
                allowed=True,
                reason="new_source_more_reliable",
            )

        if new_source_score < old_source_score:
            return MemoryDecision(
                allowed=False,
                reason="new_source_less_reliable",
            )

        if new_updated_at >= existing.updated_at:
            return MemoryDecision(
                allowed=True,
                reason="newer_or_equal_timestamp",
            )

        return MemoryDecision(
            allowed=False,
            reason="older_timestamp",
        )

    def should_update(
        self,
        existing,
        new_confidence,
        new_importance,
        new_source,
        new_updated_at,
    ):
        decision = self.evaluate(
            existing,
            new_confidence=new_confidence,
            new_importance=new_importance,
            new_source=new_source,
            new_updated_at=new_updated_at,
        )

        return decision.allowed
