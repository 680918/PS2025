import json

from evaluation.learning_pipeline import process_learning_evaluation
from memory.learning_models import LearningRecord
from memory.learning_service import LearningMemoryService
from memory.service import MemoryService
from memory.store import MemoryStore


def create_services():
    memory_service = MemoryService(MemoryStore())
    learning_service = LearningMemoryService(memory_service)

    return memory_service, learning_service


def test_learning_pipeline_updates_skill_when_evaluation_is_allowed():
    memory_service, learning_service = create_services()

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

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=60,
        )
    )

    current_record = LearningRecord(
        topic="Python",
        understanding=78,
        evidence="Python函数测验8/10",
        evidence_type="quiz",
    )

    result = process_learning_evaluation(
        learning_service,
        memory_service,
        current_record,
    )

    assert result.evaluation.status == "improving"
    assert result.evaluation.confidence == 0.85
    assert result.skill_update_decision.allowed is True
    assert result.updated_skill is not None

    updated = memory_service.get_by_key(
        "skill",
        "Python",
    )

    data = json.loads(updated.content)

    assert data["level"] == 78


def test_learning_pipeline_does_not_update_skill_when_confidence_is_low():
    memory_service, learning_service = create_services()

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

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=60,
        )
    )

    current_record = LearningRecord(
        topic="Python",
        understanding=78,
        evidence="我感觉自己掌握得不错",
        evidence_type="self_report",
    )

    result = process_learning_evaluation(
        learning_service,
        memory_service,
        current_record,
    )

    assert result.evaluation.status == "improving"
    assert result.evaluation.confidence == 0.6
    assert result.skill_update_decision.allowed is False
    assert result.updated_skill is None

    skill = memory_service.get_by_key(
        "skill",
        "Python",
    )

    data = json.loads(skill.content)

    assert data["level"] == 60


def test_learning_pipeline_does_not_update_skill_with_insufficient_data():
    memory_service, learning_service = create_services()

    memory_service.remember(
        memory_type="skill",
        memory_key="地理",
        content=json.dumps(
            {
                "level": 40,
            },
            ensure_ascii=False,
        ),
        importance=0.9,
        confidence=0.8,
        source="user_confirmed",
    )

    current_record = LearningRecord(
        topic="地理",
        understanding=70,
        evidence="完成一次地理测验",
        evidence_type="quiz",
    )

    result = process_learning_evaluation(
        learning_service,
        memory_service,
        current_record,
    )

    assert result.evaluation.status == "insufficient_data"
    assert result.skill_update_decision.allowed is False
    assert result.updated_skill is None
