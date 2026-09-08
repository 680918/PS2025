import pytest
from memory.models import MemoryRecord
from memory.store import MemoryStore


def test_memory_store_can_add_and_get_memory():

    store = MemoryStore()

    memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(memory)

    result = store.get(memory.id)

    assert result is memory


def test_memory_store_returns_none_for_unknown_id():

    store = MemoryStore()

    result = store.get("missing-id")

    assert result is None


def test_memory_store_can_list_memories_by_type():

    store = MemoryStore()

    skill_memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    profile_memory = MemoryRecord(
        memory_type="profile",
        content="用户每天可学习1小时",
        importance=0.8,
        confidence=0.95,
        source="user_profile",
    )

    store.add(skill_memory)
    store.add(profile_memory)

    results = store.list_by_type("skill")

    assert results == [skill_memory]


def test_memory_store_can_update_existing_memory():

    store = MemoryStore()

    memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(memory)

    original_updated_at = memory.updated_at

    updated_memory = store.update(
        memory.id,
        content="用户已经能够进行基础 Python 调试",
        importance=0.8,
    )

    assert updated_memory.content == "用户已经能够进行基础 Python 调试"
    assert updated_memory.importance == 0.8
    assert updated_memory.id == memory.id
    assert updated_memory.updated_at >= original_updated_at


def test_memory_store_update_rejects_invalid_importance():

    store = MemoryStore()

    memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(memory)

    with pytest.raises(ValueError):
        store.update(
            memory.id,
            importance=1.5,
        )


def test_memory_store_update_rejects_invalid_memory_type():

    store = MemoryStore()

    memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(memory)

    with pytest.raises(ValueError):
        store.update(
            memory.id,
            memory_type="unknown",
        )


def test_memory_store_failed_update_preserves_original_value():

    store = MemoryStore()

    memory = MemoryRecord(
        memory_type="skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(memory)

    with pytest.raises(ValueError):
        store.update(
            memory.id,
            importance=1.5,
        )

    stored_memory = store.get(memory.id)

    assert stored_memory.importance == 0.9


def test_memory_store_can_find_memory_by_type_and_key():

    store = MemoryStore()

    memory = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(memory)

    result = store.find_by_key(
        memory_type="skill",
        memory_key="python_skill",
    )

    assert result is memory
