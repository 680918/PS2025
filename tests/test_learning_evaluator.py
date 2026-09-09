from evaluation.learning_evaluator import evaluate_learning_progress
from memory.learning_models import LearningRecord
from memory.learning_service import LearningMemoryService
from memory.service import MemoryService
from memory.store import MemoryStore


def create_learning_service():
    memory_service = MemoryService(MemoryStore())
    return LearningMemoryService(memory_service)


def test_learning_progress_is_insufficient_with_one_record():
    learning_service = create_learning_service()

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=60,
        )
    )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "insufficient_data"


def test_learning_progress_is_improving():
    learning_service = create_learning_service()

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=60,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=72,
        )
    )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "improving"
    assert result.change == 12


def test_learning_progress_is_declining():
    learning_service = create_learning_service()

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=80,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=70,
        )
    )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "declining"
    assert result.change == -10


def test_learning_progress_is_stable():
    learning_service = create_learning_service()

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=70,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=73,
        )
    )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "stable"
    assert result.change == 3


def test_learning_progress_uses_recent_three_records_for_improving_trend():
    learning_service = create_learning_service()

    for understanding in [60, 68, 75]:
        learning_service.save(
            LearningRecord(
                topic="Python",
                understanding=understanding,
            )
        )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "improving"
    assert result.change == 15


def test_learning_progress_uses_recent_three_records_for_declining_trend():
    learning_service = create_learning_service()

    for understanding in [80, 76, 70]:
        learning_service.save(
            LearningRecord(
                topic="Python",
                understanding=understanding,
            )
        )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "declining"
    assert result.change == -10


def test_learning_progress_uses_recent_three_records_for_stable_trend():
    learning_service = create_learning_service()

    for understanding in [70, 72, 71]:
        learning_service.save(
            LearningRecord(
                topic="Python",
                understanding=understanding,
            )
        )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "stable"
    assert result.change == 1


def test_learning_progress_does_not_overreact_to_single_drop():
    learning_service = create_learning_service()

    for understanding in [60, 80, 72]:
        learning_service.save(
            LearningRecord(
                topic="Python",
                understanding=understanding,
            )
        )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "improving"
    assert result.change == 12


def test_learning_progress_has_high_confidence_with_evidence():
    learning_service = create_learning_service()

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
            evidence="能够独立写出一个简单函数",
            evidence_type="practice",
        )
    )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "improving"
    assert result.confidence == 0.75


def test_learning_progress_has_lower_confidence_without_evidence():
    learning_service = create_learning_service()

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
            evidence="",
        )
    )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "improving"
    assert result.confidence == 0.4


def test_quiz_evidence_has_higher_confidence():
    learning_service = create_learning_service()

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=60,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="Python",
            understanding=78,
            evidence="Python函数测验8/10",
            evidence_type="quiz",
        )
    )

    result = evaluate_learning_progress(
        "Python",
        learning_service,
    )

    assert result.status == "improving"
    assert result.confidence == 0.85


def test_project_evidence_has_highest_confidence():
    learning_service = create_learning_service()

    learning_service.save(
        LearningRecord(
            topic="AI Agent",
            understanding=70,
        )
    )

    learning_service.save(
        LearningRecord(
            topic="AI Agent",
            understanding=85,
            evidence="独立完成一个可运行的Agent项目",
            evidence_type="project",
        )
    )

    result = evaluate_learning_progress(
        "AI Agent",
        learning_service,
    )

    assert result.status == "improving"
    assert result.confidence == 0.95
