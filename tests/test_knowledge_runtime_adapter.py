from coach.knowledge.runtime_adapter import (
    build_curation_context,
)


def test_adapter_should_build_progress_and_evidence():

    progress, evidences = build_curation_context(
        {
            "topic": "Memory Retrieval",
            "learning_count": 5,
            "understanding_score": 85,
            "completed_tasks": 3,
            "practice_count": 4,
            "session_id": "session-001",
            "task": "完成测试",
            "result": "通过",
            "assessment": "理解良好",
            "tests_passed": 3,
            "tests_total": 3,
        }
    )

    assert progress.topic == "Memory Retrieval"

    assert evidences[0].session_id == "session-001"
