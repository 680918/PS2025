from memory.service import MemoryService
from memory.store import MemoryStore
from memory.sqlite_store import SQLiteMemoryStore
from memory.adapters import (
    get_skill_map_from_memory,
    get_user_profile_from_memory,
)

from memory.migration import (
    ensure_skill_map_migrated,
    ensure_user_profile_migrated,
    migrate_skill_map,
    migrate_user_profile,
)


def test_migrate_user_profile_preserves_profile_data():

    store = MemoryStore()
    service = MemoryService(store)

    migrate_user_profile(service)

    result = get_user_profile_from_memory(service)

    data = result["data"]

    assert data["age"] == 58
    assert data["technical_level"] == "技术入门阶段"
    assert data["goal"] == "一年内掌握AI Agent应用搭建能力"
    assert data["daily_learning_time"] == "1小时"
    assert data["preferred_learning_time"] == "下午3点左右"

    assert "原理" in data["learning_preferences"]
    assert "喜欢理解底层逻辑" in data["strength"]
    assert "Python实践不足" in data["weakness"]


def test_migrate_user_profile_to_sqlite(tmp_path):

    db_path = tmp_path / "memory.db"

    store = SQLiteMemoryStore(db_path)
    service = MemoryService(store)

    migrate_user_profile(service)

    new_store = SQLiteMemoryStore(db_path)
    new_service = MemoryService(new_store)

    result = get_user_profile_from_memory(new_service)

    assert result["data"]["age"] == 58
    assert result["data"]["daily_learning_time"] == "1小时"


def test_ensure_user_profile_migrated_migrates_when_missing():

    store = MemoryStore()
    service = MemoryService(store)

    migrated = ensure_user_profile_migrated(service)

    assert migrated is True

    memory = service.get_by_key(
        "profile",
        "goal",
    )

    assert memory is not None


def test_ensure_user_profile_migrated_does_not_duplicate():

    store = MemoryStore()
    service = MemoryService(store)

    first = ensure_user_profile_migrated(service)
    second = ensure_user_profile_migrated(service)

    assert first is True
    assert second is False

    memories = store.list_by_type("profile")

    assert len(memories) == 8


def test_migrate_skill_map_preserves_skill_contract():

    service = MemoryService(MemoryStore())

    migrate_skill_map(service)

    result = get_skill_map_from_memory(service)

    assert result["status"] == "success"

    assert result["data"]["Python"]["level"] == 15
    assert result["data"]["AI Agent"]["level"] == 90

    assert "缺少调试经验" in result["data"]["Python"]["weakness"]


def test_ensure_skill_map_migrated_does_not_duplicate():

    store = MemoryStore()
    service = MemoryService(store)

    first = ensure_skill_map_migrated(service)
    second = ensure_skill_map_migrated(service)

    assert first is True
    assert second is False

    memories = store.list_by_type("skill")

    assert len(memories) == 2


def test_skill_map_migration_persists_in_sqlite(tmp_path):

    db_path = tmp_path / "memory.db"

    store = SQLiteMemoryStore(db_path)
    service = MemoryService(store)

    migrate_skill_map(service)

    new_store = SQLiteMemoryStore(db_path)
    new_service = MemoryService(new_store)

    result = get_skill_map_from_memory(new_service)

    assert result["data"]["Python"]["level"] == 15
    assert result["data"]["AI Agent"]["level"] == 90
