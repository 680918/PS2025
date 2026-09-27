import json

from learning.journey_completion_report import (
    JourneyCompletionReport,
)
from memory.service import MemoryService
from memory.store import MemoryStore
from memory.journey_memory_consolidation_service import (
    consolidate_journey_completion_summary,
)


def test_completion_report_should_be_consolidated_into_learning_memory():
    memory_service = MemoryService(MemoryStore())

    report = JourneyCompletionReport(
        journey_id="journey_001",
        user_id="user_001",
        summary={
            "journey_id": "journey_001",
            "domain": "Python",
            "goal": "完成 Python 基础学习",
            "status": "completed",
            "completed_sessions": 2,
            "first_understanding": 60,
            "latest_understanding": 85,
            "understanding_change": 25,
            "trend": "improving",
            "evidence_count": 2,
            "completed_tasks": 2,
            "learning_signal": "positive",
            "quality_summary": {
                "strong": 2,
                "weak": 0,
                "insufficient": 0,
            },
        },
        commentary="这是一段 LLM 生成的毕业评语。",
    )

    memory = consolidate_journey_completion_summary(
        summary=report.summary,
        memory_service=memory_service,
    )

    assert memory.memory_type == "learning"

    assert memory.memory_key == "journey_completion:journey_001"

    assert memory.source == "journey_completion_report"

    content = json.loads(memory.content)

    assert content["domain"] == "Python"
    assert content["goal"] == "完成 Python 基础学习"
    assert content["latest_understanding"] == 85
    assert content["understanding_change"] == 25
    assert content["trend"] == "improving"
    assert content["evidence_count"] == 2

    assert "commentary" not in content


def test_same_journey_should_not_create_duplicate_learning_memory():
    memory_service = MemoryService(MemoryStore())

    report = JourneyCompletionReport(
        journey_id="journey_001",
        user_id="user_001",
        summary={
            "journey_id": "journey_001",
            "domain": "Python",
            "goal": "完成 Python 基础学习",
            "status": "completed",
            "completed_sessions": 2,
            "first_understanding": 60,
            "latest_understanding": 85,
            "understanding_change": 25,
            "trend": "improving",
            "evidence_count": 2,
            "completed_tasks": 2,
            "learning_signal": "positive",
            "quality_summary": {
                "strong": 2,
                "weak": 0,
                "insufficient": 0,
            },
        },
        commentary="毕业评语。",
    )

    first_memory = consolidate_journey_completion_summary(
        summary=report.summary,
        memory_service=memory_service,
    )

    second_memory = consolidate_journey_completion_summary(
        summary=report.summary,
        memory_service=memory_service,
    )

    memories = memory_service.store.list_by_type("learning")

    assert len(memories) == 1

    assert first_memory.id == second_memory.id

    assert memories[0].memory_key == "journey_completion:journey_001"


def test_consolidated_journey_memory_should_survive_service_restart(
    tmp_path,
):
    from memory.sqlite_store import SQLiteMemoryStore

    database_path = tmp_path / "memory.db"

    first_memory_service = MemoryService(SQLiteMemoryStore(database_path))

    report = JourneyCompletionReport(
        journey_id="journey_001",
        user_id="user_001",
        summary={
            "journey_id": "journey_001",
            "domain": "Python",
            "goal": "完成 Python 基础学习",
            "status": "completed",
            "completed_sessions": 2,
            "first_understanding": 60,
            "latest_understanding": 85,
            "understanding_change": 25,
            "trend": "improving",
            "evidence_count": 2,
            "completed_tasks": 2,
            "learning_signal": "positive",
            "quality_summary": {
                "strong": 2,
                "weak": 0,
                "insufficient": 0,
            },
        },
        commentary="这是一段毕业评语。",
    )

    consolidate_journey_completion_summary(
        summary=report.summary,
        memory_service=first_memory_service,
    )

    # 模拟应用重启：重新创建 Store 和 Service。
    second_memory_service = MemoryService(SQLiteMemoryStore(database_path))

    saved_memory = second_memory_service.get_by_key(
        "learning",
        "journey_completion:journey_001",
    )

    assert saved_memory is not None
    assert saved_memory.memory_type == "learning"
    assert saved_memory.source == "journey_completion_report"

    content = json.loads(saved_memory.content)

    assert content["domain"] == "Python"
    assert content["latest_understanding"] == 85
    assert content["understanding_change"] == 25
