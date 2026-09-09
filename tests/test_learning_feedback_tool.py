import json

from memory.service import MemoryService
from memory.store import MemoryStore
from tools.tools import save_learning_feedback, execute_tool


def test_save_learning_feedback_updates_skill_when_evidence_is_strong():
    memory_service = MemoryService(MemoryStore())

    memory_service.remember(
        memory_type="skill",
        memory_key="Python",
        content=json.dumps(
            {
                "level": 60,
            },
            ensure_ascii=False,
        ),
        importance=0.9,
        confidence=0.8,
        source="user_confirmed",
    )

    save_learning_feedback(
        topic="Python",
        understanding=60,
        memory_service=memory_service,
    )

    result = save_learning_feedback(
        topic="Python",
        understanding=80,
        evidence="完成Python函数测验，得分8/10",
        evidence_type="quiz",
        memory_service=memory_service,
    )

    assert result["status"] == "success"
    assert result["data"]["evaluation_status"] == "improving"
    assert result["data"]["evaluation_confidence"] == 0.85
    assert result["data"]["skill_update_allowed"] is True
    assert result["data"]["skill_updated"] is True

    skill = memory_service.get_by_key(
        "skill",
        "Python",
    )

    data = json.loads(skill.content)

    assert data["level"] == 80


def test_save_learning_feedback_requires_memory_service():
    result = save_learning_feedback(
        topic="Python",
        understanding=80,
    )

    assert result["status"] == "error"
    assert result["tool_name"] == "save_learning_feedback"


def test_execute_tool_injects_memory_service_for_learning_feedback():
    memory_service = MemoryService(MemoryStore())

    result = execute_tool(
        "save_learning_feedback",
        arguments={
            "topic": "摄影",
            "understanding": 70,
            "evidence": "完成一次曝光练习",
            "evidence_type": "practice",
        },
        memory_service=memory_service,
    )

    assert result["status"] == "success"

    learning_memories = memory_service.store.list_by_type("learning")

    assert len(learning_memories) == 1
