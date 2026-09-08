from memory.models import MemoryRecord
from memory.policy import MemoryPolicy


def test_memory_policy_allows_equal_or_higher_confidence():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.9,
        confidence=0.8,
        source="learning_feedback",
        updated_at="2026-09-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.8,
            new_importance=0.9,
            new_source="learning_feedback",
            new_updated_at="2026-09-01T10:00:00",
        )
        is True
    )

    assert (
        policy.should_update(
            existing,
            new_confidence=0.9,
            new_importance=0.5,
            new_source="learning_feedback",
            new_updated_at="2026-09-01T10:00:00",
        )
        is True
    )


def test_memory_policy_rejects_lower_confidence():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.9,
        confidence=0.9,
        source="learning_feedback",
        updated_at="2026-09-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.6,
            new_importance=1.0,
            new_source="learning_feedback",
            new_updated_at="2026-09-01T10:00:00",
        )
        is False
    )


def test_memory_policy_rejects_lower_importance_when_confidence_is_equal():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.9,
        confidence=0.8,
        source="learning_feedback",
        updated_at="2026-09-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.8,
            new_importance=0.6,
            new_source="learning_feedback",
            new_updated_at="2026-09-01T10:00:00",
        )
        is False
    )


def test_memory_policy_allows_equal_or_higher_importance_when_confidence_is_equal():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.7,
        confidence=0.8,
        source="learning_feedback",
        updated_at="2026-09-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.8,
            new_importance=0.7,
            new_source="learning_feedback",
            new_updated_at="2026-09-01T10:00:00",
        )
        is True
    )

    assert (
        policy.should_update(
            existing,
            new_confidence=0.8,
            new_importance=0.9,
            new_source="learning_feedback",
            new_updated_at="2026-09-01T10:00:00",
        )
        is True
    )


def test_memory_policy_prefers_more_reliable_source_when_other_scores_equal():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
        updated_at="2026-09-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.9,
            new_importance=0.8,
            new_source="agent_inference",
            new_updated_at="2026-09-01T10:00:00",
        )
        is False
    )


def test_memory_policy_allows_more_reliable_source_when_other_scores_equal():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.8,
        confidence=0.9,
        source="agent_inference",
        updated_at="2026-09-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.9,
            new_importance=0.8,
            new_source="user_confirmed",
            new_updated_at="2026-09-01T10:00:00",
        )
        is True
    )


def test_memory_policy_prefers_newer_information_when_other_scores_equal():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.8,
        confidence=0.9,
        source="learning_feedback",
        updated_at="2026-08-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.9,
            new_importance=0.8,
            new_source="learning_feedback",
            new_updated_at="2026-09-01T10:00:00",
        )
        is True
    )


def test_memory_policy_rejects_older_information_when_other_scores_equal():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.8,
        confidence=0.9,
        source="learning_feedback",
        updated_at="2026-09-01T10:00:00",
    )

    policy = MemoryPolicy()

    assert (
        policy.should_update(
            existing,
            new_confidence=0.9,
            new_importance=0.8,
            new_source="learning_feedback",
            new_updated_at="2026-08-01T10:00:00",
        )
        is False
    )


def test_memory_policy_explains_lower_confidence_rejection():

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="旧记忆",
        importance=0.8,
        confidence=0.9,
        source="learning_feedback",
        updated_at="2026-08-01T10:00:00",
    )

    policy = MemoryPolicy()

    decision = policy.evaluate(
        existing,
        new_confidence=0.6,
        new_importance=0.9,
        new_source="user_confirmed",
        new_updated_at="2026-09-01T10:00:00",
    )

    assert decision.allowed is False
    assert decision.reason == "new_confidence_lower"
