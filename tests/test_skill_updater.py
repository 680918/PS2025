import json

from evaluation.learning_evaluator import LearningProgressResult
from evaluation.skill_updater import update_skill_from_evaluation
from memory.service import MemoryService
from memory.store import MemoryStore


def test_update_skill_from_evaluation_updates_skill_level():
    service = MemoryService(MemoryStore())

    service.remember(
        memory_type="skill",
        memory_key="Python",
        content=json.dumps(
            {
                "level": 60,
                "weakness": ["函数参数"],
            },
            ensure_ascii=False,
        ),
        importance=0.9,
        confidence=0.8,
        source="user_confirmed",
    )

    evaluation = LearningProgressResult(
        topic="Python",
        status="improving",
        previous_understanding=60,
        current_understanding=78,
        change=18,
        confidence=0.85,
        reason="Improving.",
    )

    update_skill_from_evaluation(
        service,
        evaluation,
    )

    updated = service.get_by_key(
        "skill",
        "Python",
    )

    data = json.loads(updated.content)

    assert data["level"] == 78
    assert data["evaluation_status"] == "improving"
    assert data["evaluation_confidence"] == 0.85


def test_update_skill_returns_none_when_skill_does_not_exist():
    service = MemoryService(MemoryStore())

    evaluation = LearningProgressResult(
        topic="地理",
        status="improving",
        previous_understanding=50,
        current_understanding=70,
        change=20,
        confidence=0.85,
        reason="Improving.",
    )

    result = update_skill_from_evaluation(
        service,
        evaluation,
    )

    assert result is None


def test_skill_update_can_replace_high_confidence_old_skill_state():
    import json

    from evaluation.learning_evaluator import LearningProgressResult
    from evaluation.skill_updater import update_skill_from_evaluation
    from memory.service import MemoryService
    from memory.store import MemoryStore

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

    evaluation = LearningProgressResult(
        topic="Python函数",
        status="improving",
        previous_understanding=80,
        current_understanding=90,
        change=10,
        confidence=0.85,
        reason="Learning progress is improving.",
    )

    updated = update_skill_from_evaluation(
        memory_service,
        evaluation,
    )

    assert updated is not None

    skill = memory_service.get_by_key(
        "skill",
        "Python",
    )

    skill_data = json.loads(skill.content)

    assert skill_data["level"] == 90
    assert skill_data["evaluation_status"] == "improving"
    assert skill_data["evaluation_confidence"] == 0.85

    assert skill.confidence == 0.85
    assert skill.source == "learning_evaluation"
