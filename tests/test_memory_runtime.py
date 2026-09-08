from memory.runtime import create_memory_service
from memory.service import MemoryService
from memory.sqlite_store import SQLiteMemoryStore


def test_create_memory_service_uses_sqlite_store(tmp_path):

    db_path = tmp_path / "memory.db"

    service = create_memory_service(db_path)

    assert isinstance(service, MemoryService)
    assert isinstance(service.store, SQLiteMemoryStore)


def test_create_memory_service_creates_database_directory(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    service = create_memory_service()

    service.remember(
        memory_type="skill",
        memory_key="python_skill",
        content="用户正在学习 Python",
        importance=0.8,
        confidence=0.9,
        source="user_confirmed",
    )

    assert (tmp_path / "data" / "memory.db").exists()


def test_create_memory_service_migrates_skill_map(tmp_path):
    db_path = tmp_path / "memory.db"

    service = create_memory_service(db_path)

    python_skill = service.get_by_key(
        "skill",
        "Python",
    )

    ai_agent_skill = service.get_by_key(
        "skill",
        "AI Agent",
    )

    assert python_skill is not None
    assert ai_agent_skill is not None


def test_create_memory_service_does_not_duplicate_skill_migration(tmp_path):
    db_path = tmp_path / "memory.db"

    first_service = create_memory_service(db_path)
    first_skills = first_service.store.list_by_type("skill")

    second_service = create_memory_service(db_path)
    second_skills = second_service.store.list_by_type("skill")

    assert len(second_skills) == len(first_skills)
