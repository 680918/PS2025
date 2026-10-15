from coach.knowledge.evidence_builder import (
    build_learning_progress,
    build_learning_evidence,
)


def test_builder_should_create_learning_progress():

    progress = build_learning_progress(
        {
            "topic": "Memory Retrieval",
            "learning_count": 5,
            "understanding_score": 85,
            "completed_tasks": 3,
            "practice_count": 4,
        }
    )

    assert progress.topic == "Memory Retrieval"

    assert progress.learning_count == 5


def test_builder_should_create_learning_evidence():

    evidence = build_learning_evidence(
        {
            "session_id": "session-001",
            "task": "完成测试",
            "result": "通过3个测试",
            "assessment": "理解较好",
            "tests_passed": 3,
            "tests_total": 3,
        }
    )

    assert evidence.session_id == "session-001"

    assert evidence.tests_passed == 3
