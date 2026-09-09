import pytest

from memory.learning_models import LearningRecord


def test_learning_record_stores_learning_result():
    record = LearningRecord(
        topic="Tool Calling",
        understanding=70,
        difficulty="Tool 和 Skill 边界不清",
        evidence="能够解释 Tool Calling 基本流程",
        next_step="继续练习多 Tool 调用",
    )

    assert record.topic == "Tool Calling"
    assert record.understanding == 70
    assert record.difficulty == "Tool 和 Skill 边界不清"
    assert record.id is not None
    assert record.created_at is not None


def test_learning_record_rejects_invalid_understanding():
    with pytest.raises(ValueError):
        LearningRecord(
            topic="Python",
            understanding=120,
        )


def test_learning_record_rejects_empty_topic():
    with pytest.raises(ValueError):
        LearningRecord(
            topic="",
            understanding=60,
        )
