from coach.knowledge.curator import (
    KnowledgeCurationEngine,
)

from learning.progress import (
    LearningProgress,
)

from learning.evidence import (
    LearningEvidence,
)


def test_engine_should_create_candidate_from_learning_progress_and_evidence():

    engine = KnowledgeCurationEngine()

    progress = LearningProgress(
        topic="Memory Retrieval",
        learning_count=5,
        understanding_score=85,
        completed_tasks=3,
        practice_count=4,
    )

    evidence = LearningEvidence(
        session_id="session-001",
        task="完成 Memory Retrieval 测试",
        result="通过3个测试",
        assessment="理解较好",
        tests_passed=3,
        tests_total=3,
    )

    candidate = engine.evaluate(
        progress,
        [
            evidence,
        ],
    )

    assert candidate is not None

    assert candidate.topic == "Memory Retrieval"
