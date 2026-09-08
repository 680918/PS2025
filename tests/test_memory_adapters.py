import json

from memory.adapters import (
    get_user_profile_from_memory,
    get_skill_map_from_memory,
)
from memory.service import MemoryService
from memory.store import MemoryStore


def test_get_user_profile_from_memory():

    store = MemoryStore()
    service = MemoryService(store)

    service.remember(
        memory_type="profile",
        memory_key="age",
        content="58",
        importance=0.8,
        confidence=1.0,
        source="user_confirmed",
    )

    service.remember(
        memory_type="profile",
        memory_key="daily_learning_time",
        content="1小时",
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    service.remember(
        memory_type="profile",
        memory_key="learning_preferences",
        content=json.dumps(
            ["原理", "实践", "结构"],
            ensure_ascii=False,
        ),
        importance=0.8,
        confidence=1.0,
        source="user_confirmed",
    )

    result = get_user_profile_from_memory(service)

    assert result["status"] == "success"
    assert result["tool_name"] == "get_user_profile"

    assert result["data"]["age"] == 58
    assert result["data"]["daily_learning_time"] == "1小时"

    assert result["data"]["learning_preferences"] == [
        "原理",
        "实践",
        "结构",
    ]


def test_get_skill_map_from_memory():

    service = MemoryService(MemoryStore())

    service.remember(
        memory_type="skill",
        memory_key="Python",
        content=json.dumps(
            {
                "level": 15,
                "weakness": [
                    "不熟悉Python开发",
                    "缺少调试经验",
                ],
            },
            ensure_ascii=False,
        ),
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    service.remember(
        memory_type="skill",
        memory_key="AI Agent",
        content=json.dumps(
            {
                "level": 90,
                "evidence": [
                    "理解Controller、LLM、Tool、Memory关系",
                ],
            },
            ensure_ascii=False,
        ),
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    result = get_skill_map_from_memory(service)

    assert result["status"] == "success"
    assert result["tool_name"] == "get_skill_map"

    assert result["data"]["Python"]["level"] == 15
    assert result["data"]["AI Agent"]["level"] == 90
