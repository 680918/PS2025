from memory.models import MemoryRecord
from memory.sqlite_store import SQLiteMemoryStore


def test_sqlite_memory_store_adds_and_gets_memory(tmp_path):

    db_path = tmp_path / "memory.db"

    store = SQLiteMemoryStore(db_path)

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
    assert loaded.memory_type == "skill"
    assert loaded.memory_key == "python_skill"
    assert loaded.content == "用户正在学习 Python"
    assert loaded.importance == 0.8
    assert loaded.confidence == 0.9
    assert loaded.source == "user_confirmed"


def test_sqlite_memory_store_lists_memories_by_type(tmp_path):

    db_path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(db_path)

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
    assert results[0].memory_key == "python_skill"


def test_sqlite_memory_store_finds_memory_by_type_and_key(tmp_path):

    db_path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(db_path)

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
    assert result.content == "用户正在学习 Python"


def test_sqlite_memory_store_returns_none_when_key_not_found(tmp_path):

    db_path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(db_path)

    result = store.find_by_key(
        memory_type="skill",
        memory_key="python_skill",
    )

    assert result is None


def test_sqlite_memory_store_updates_existing_memory(tmp_path):

    db_path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(db_path)

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


def test_sqlite_memory_store_update_returns_none_when_memory_not_found(tmp_path):

    db_path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(db_path)

    result = store.update(
        "missing-id",
        content="不会被保存",
    )

    assert result is None


def test_sqlite_memory_store_persists_across_instances(tmp_path):

    db_path = tmp_path / "memory.db"

    first_store = SQLiteMemoryStore(db_path)

    memory = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户已经开始进行 Python 实践",
        importance=0.9,
        confidence=0.9,
        source="user_confirmed",
    )

    first_store.add(memory)

    second_store = SQLiteMemoryStore(db_path)

    loaded = second_store.get(memory.id)

    assert loaded is not None
    assert loaded.id == memory.id
    assert loaded.memory_key == "python_skill"
    assert loaded.content == "用户已经开始进行 Python 实践"
