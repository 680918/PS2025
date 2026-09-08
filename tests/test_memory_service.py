from memory.models import MemoryRecord
from memory.service import MemoryService
from memory.store import MemoryStore
from memory.sqlite_store import SQLiteMemoryStore


def test_memory_service_adds_new_memory_when_key_not_found():

    store = MemoryStore()
    service = MemoryService(store)

    result = service.remember(
        memory_type="skill",
        memory_key="python_skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    stored = store.find_by_key(
        memory_type="skill",
        memory_key="python_skill",
    )

    assert result is stored
    assert stored.content == "用户 Python 实践能力较弱"


def test_memory_service_updates_existing_memory_when_key_exists():

    store = MemoryStore()

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户 Python 实践能力较弱",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(existing)

    service = MemoryService(store)

    result = service.remember(
        memory_type="skill",
        memory_key="python_skill",
        content="用户已经能够进行基础 Python 调试",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    assert result.id == existing.id
    assert result.content == "用户已经能够进行基础 Python 调试"
    assert result.importance == 0.9


def test_memory_service_does_not_overwrite_with_lower_confidence():

    store = MemoryStore()

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户已经能够进行基础 Python 调试",
        importance=0.9,
        confidence=0.95,
        source="learning_feedback",
    )

    store.add(existing)

    service = MemoryService(store)

    result = service.remember(
        memory_type="skill",
        memory_key="python_skill",
        content="用户 Python 完全不会调试",
        importance=0.8,
        confidence=0.60,
        source="single_observation",
    )

    stored = store.find_by_key(
        memory_type="skill",
        memory_key="python_skill",
    )

    assert stored.content == "用户已经能够进行基础 Python 调试"
    assert stored.confidence == 0.95
    assert result is stored


def test_memory_service_exposes_rejection_reason():

    store = MemoryStore()

    existing = MemoryRecord(
        memory_type="skill",
        memory_key="python_skill",
        content="用户已经掌握基础 Python",
        importance=0.9,
        confidence=0.9,
        source="user_confirmed",
        updated_at="2026-09-01T10:00:00",
    )

    store.add(existing)

    service = MemoryService(store)

    result = service.remember_with_result(
        memory_type="skill",
        memory_key="python_skill",
        content="用户完全不会 Python",
        importance=0.9,
        confidence=0.6,
        source="agent_inference",
    )

    assert result.memory.id == existing.id
    assert result.action == "kept"
    assert result.reason == "new_confidence_lower"
    assert result.memory_type == "skill"
    assert result.memory_key == "python_skill"


def test_memory_service_reports_added_action():

    store = MemoryStore()
    service = MemoryService(store)

    result = service.remember_with_result(
        memory_type="skill",
        memory_key="python_skill",
        content="用户开始学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    assert result.action == "added"
    assert result.reason == "new_memory"
    assert result.memory_type == "skill"
    assert result.memory_key == "python_skill"


def test_memory_service_uses_persistent_sqlite_memory(tmp_path):

    db_path = tmp_path / "memory.db"

    first_store = SQLiteMemoryStore(db_path)
    first_service = MemoryService(first_store)

    first_result = first_service.remember_with_result(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    assert first_result.action == "added"

    second_store = SQLiteMemoryStore(db_path)
    second_service = MemoryService(second_store)

    loaded = second_store.find_by_key(
        memory_type="skill",
        memory_key="python_skill",
    )

    assert loaded is not None
    assert loaded.content == "用户正在学习 Python"

    second_result = second_service.remember_with_result(
        memory_type="skill",
        memory_key="python_skill",
        content="用户已经能够进行基础 Python 调试",
        importance=0.9,
        confidence=0.95,
        source="user_confirmed",
    )

    assert second_result.action == "updated"
    assert second_result.memory.id == first_result.memory.id
    assert second_result.memory.content == "用户已经能够进行基础 Python 调试"


def test_memory_service_get_context_returns_grouped_memories():

    store = MemoryStore()
    service = MemoryService(store)

    service.remember(
        memory_type="profile",
        memory_key="learning_goal",
        content="用户希望一年内掌握 AI Agent 搭建能力",
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    service.remember(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    context = service.get_context()

    assert "profile" in context
    assert "skill" in context
    assert "learning" in context
    assert "project" in context
    assert "experience" in context

    assert len(context["profile"]) == 1
    assert len(context["skill"]) == 1

    assert context["profile"][0]["memory_key"] == "learning_goal"
    assert context["skill"][0]["memory_key"] == "python_skill"


def test_memory_service_get_by_key():

    store = MemoryStore()
    service = MemoryService(store)

    service.remember(
        memory_type="profile",
        memory_key="daily_learning_time",
        content="1小时",
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    memory = service.get_by_key(
        "profile",
        "daily_learning_time",
    )

    assert memory is not None
    assert memory.memory_key == "daily_learning_time"
    assert memory.content == "1小时"


def test_memory_service_get_by_key_returns_none_when_missing():

    store = MemoryStore()
    service = MemoryService(store)

    memory = service.get_by_key(
        "profile",
        "daily_learning_time",
    )

    assert memory is None
