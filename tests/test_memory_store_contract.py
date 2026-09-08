import pytest

from memory.models import MemoryRecord
from memory.store import MemoryStore
from memory.sqlite_store import SQLiteMemoryStore


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        return MemoryStore()

    db_path = tmp_path / "memory.db"
    return SQLiteMemoryStore(db_path)


def test_store_contract_add_and_get(store):

    memory = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    store.add(memory)

    loaded = store.get(memory.id)

    assert loaded is not None
    assert loaded.id == memory.id
    assert loaded.content == memory.content


def test_store_contract_find_by_key(store):

    memory = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    store.add(memory)

    result = store.find_by_key(
        memory_type="skill",
        memory_key="python_skill",
    )

    assert result is not None
    assert result.id == memory.id


def test_store_contract_list_by_type(store):

    skill_memory = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    profile_memory = MemoryRecord(
        memory_type="profile",
        memory_key="learning_style",
        content="用户喜欢先理解原理再实践",
        importance=0.9,
        confidence=0.95,
        source="user_confirmed",
    )

    store.add(skill_memory)
    store.add(profile_memory)

    results = store.list_by_type("skill")

    assert len(results) == 1
    assert results[0].memory_type == "skill"


def test_store_contract_update(store):

    memory = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.8,
        source="agent_inference",
    )

    store.add(memory)

    updated = store.update(
        memory.id,
        content="用户已经能够进行基础 Python 调试",
        importance=0.9,
        confidence=0.9,
        source="user_confirmed",
    )

    assert updated is not None
    assert updated.id == memory.id
    assert updated.content == "用户已经能够进行基础 Python 调试"
    assert updated.importance == 0.9
    assert updated.confidence == 0.9
    assert updated.source == "user_confirmed"


def test_store_contract_rejects_forbidden_update_field(store):

    memory = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    store.add(memory)

    with pytest.raises(ValueError):
        store.update(
            memory.id,
            id="changed-id",
        )
