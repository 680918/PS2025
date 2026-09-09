from memory.learning_models import LearningRecord
from memory.learning_service import LearningMemoryService
from memory.service import MemoryService
from memory.store import MemoryStore


def test_learning_memory_service_saves_record():
    memory_service = MemoryService(MemoryStore())
    learning_service = LearningMemoryService(memory_service)

    record = LearningRecord(
        topic="Python",
        understanding=70,
        difficulty="参数理解不够",
        evidence="能写简单函数",
        next_step="继续练习返回值",
    )

    learning_service.save(record)

    memories = memory_service.store.list_by_type("learning")

    assert len(memories) == 1
    assert memories[0].memory_key == record.id


def test_learning_memory_service_keeps_multiple_records_for_same_topic():
    memory_service = MemoryService(MemoryStore())
    learning_service = LearningMemoryService(memory_service)

    first = LearningRecord(
        topic="Python",
        understanding=60,
    )

    second = LearningRecord(
        topic="Python",
        understanding=75,
    )

    learning_service.save(first)
    learning_service.save(second)

    records = learning_service.list_records()

    assert len(records) == 2

    understandings = [record.understanding for record in records]

    assert 60 in understandings
    assert 75 in understandings


def test_get_history_filters_by_topic():
    memory_service = MemoryService(MemoryStore())
    learning_service = LearningMemoryService(memory_service)

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=60,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=75,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="AI Agent",
            understanding=80,
        )
    )

    records = learning_service.get_history("Python")

    assert len(records) == 2
    assert all(record.topic == "Python" for record in records)


def test_get_history_returns_all_records_when_topic_is_none():
    memory_service = MemoryService(MemoryStore())
    learning_service = LearningMemoryService(memory_service)

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=60,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="AI Agent",
            understanding=80,
        )
    )

    records = learning_service.get_history()

    assert len(records) == 2
