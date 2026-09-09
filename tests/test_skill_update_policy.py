from evaluation.learning_evaluator import LearningProgressResult
from evaluation.skill_update_policy import should_update_skill


def test_skill_update_rejected_when_data_is_insufficient():
    result = LearningProgressResult(
        topic="Python",
        status="insufficient_data",
        previous_understanding=None,
        current_understanding=None,
        change=None,
        confidence=0.0,
        reason="Not enough data.",
    )

    decision = should_update_skill(result)

    assert decision.allowed is False


def test_skill_update_rejected_when_confidence_is_low():
    result = LearningProgressResult(
        topic="Python",
        status="improving",
        previous_understanding=60,
        current_understanding=75,
        change=15,
        confidence=0.6,
        reason="Improving.",
    )

    decision = should_update_skill(result)

    assert decision.allowed is False


def test_skill_update_rejected_when_progress_is_stable():
    result = LearningProgressResult(
        topic="Python",
        status="stable",
        previous_understanding=70,
        current_understanding=72,
        change=2,
        confidence=0.85,
        reason="Stable.",
    )

    decision = should_update_skill(result)

    assert decision.allowed is False


def test_skill_update_allowed_when_progress_is_improving_with_high_confidence():
    result = LearningProgressResult(
        topic="Python",
        status="improving",
        previous_understanding=60,
        current_understanding=78,
        change=18,
        confidence=0.85,
        reason="Improving.",
    )

    decision = should_update_skill(result)

    assert decision.allowed is True


def test_skill_update_allowed_when_progress_is_declining_with_high_confidence():
    result = LearningProgressResult(
        topic="Python",
        status="declining",
        previous_understanding=80,
        current_understanding=68,
        change=-12,
        confidence=0.85,
        reason="Declining.",
    )

    decision = should_update_skill(result)

    assert decision.allowed is True
