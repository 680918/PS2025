import pytest

from evaluation.skill_resolver import resolve_skill_key
from memory.service import MemoryService
from memory.store import MemoryStore

pytestmark = pytest.mark.unit


def test_resolve_skill_key_exact_match():
    store = MemoryStore()
    memory_service = MemoryService(store)

    memory_service.remember(
        memory_type="skill",
        memory_key="Python",
        content='{"level": 15}',
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    result = resolve_skill_key(
        "Python",
        memory_service,
    )

    assert result == "Python"


def test_resolve_skill_key_parent_skill_match():
    store = MemoryStore()
    memory_service = MemoryService(store)

    memory_service.remember(
        memory_type="skill",
        memory_key="Python",
        content='{"level": 15}',
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    result = resolve_skill_key(
        "Python函数",
        memory_service,
    )

    assert result == "Python"


def test_resolve_skill_key_returns_none_when_no_match():
    store = MemoryStore()
    memory_service = MemoryService(store)

    memory_service.remember(
        memory_type="skill",
        memory_key="摄影",
        content='{"level": 42}',
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    result = resolve_skill_key(
        "Python函数",
        memory_service,
    )

    assert result is None
