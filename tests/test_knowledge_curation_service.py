from coach.knowledge.curation_service import (
    detect_runtime_knowledge_candidate,
)


def test_service_should_detect_candidate_from_learning_context():

    candidate = detect_runtime_knowledge_candidate(
        {
            "topic": "Memory Retrieval",
            "learning_count": 5,
            "understanding_score": 85,
            "completed_tasks": 3,
            "practice_count": 4,
            "session_id": "session-001",
            "task": "完成测试",
            "result": "通过3个测试",
            "assessment": "理解良好",
            "tests_passed": 3,
            "tests_total": 3,
        }
    )

    assert candidate is not None

    assert candidate.topic == "Memory Retrieval"
