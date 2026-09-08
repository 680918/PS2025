import pytest
from memory.models import MemoryRecord


def test_memory_record_creates_required_metadata():

    memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    assert memory.memory_type == "skill"
    assert memory.content == "用户 Python 实践能力较弱"

    assert memory.id is not None
    assert memory.created_at is not None
    assert memory.updated_at is not None


def test_memory_record_rejects_invalid_importance():

    with pytest.raises(ValueError):
        MemoryRecord(
            memory_type="skill",
            content="用户 Python 实践能力较弱",
            importance=1.5,
            confidence=0.95,
            source="learning_feedback",
        )


def test_memory_record_rejects_invalid_confidence():

    with pytest.raises(ValueError):
        MemoryRecord(
            memory_type="skill",
            content="用户 Python 实践能力较弱",
            importance=0.9,
            confidence=-0.1,
            source="learning_feedback",
        )


def test_memory_record_rejects_unknown_memory_type():

    with pytest.raises(ValueError):
        MemoryRecord(
            memory_type="unknown",
            content="测试记忆",
            importance=0.5,
            confidence=0.8,
            source="test",
        )


def test_memory_record_can_have_memory_key():

    memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
        memory_key="python_skill",
    )

    assert memory.memory_key == "python_skill"
