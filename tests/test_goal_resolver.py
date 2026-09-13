from memory.service import MemoryService
from memory.store import MemoryStore
from planning.goal_resolver import resolve_goal


def test_should_resolve_goal_from_profile_memory():
    store = MemoryStore()
    memory_service = MemoryService(store)

    memory_service.remember(
        memory_type="profile",
        memory_key="goal",
        content="AI Agent",
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    goal = resolve_goal(memory_service)

    assert goal == "AI Agent"


def test_missing_goal_should_return_none():
    store = MemoryStore()
    memory_service = MemoryService(store)

    goal = resolve_goal(memory_service)

    assert goal is None


def test_none_memory_service_should_return_none():
    goal = resolve_goal(None)

    assert goal is None
