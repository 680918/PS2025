from coach.knowledge.candidate import (
    KnowledgeCandidate,
)


def test_candidate_should_have_unique_identity():

    from datetime import datetime

    first = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="学习完成",
        confidence=0.9,
        created_at=datetime.now(),
    )

    second = KnowledgeCandidate(
        topic="Python",
        candidate_type="tutorial",
        reason="学习完成",
        confidence=0.8,
        created_at=datetime.now(),
    )

    assert first.candidate_id

    assert second.candidate_id

    assert first.candidate_id != second.candidate_id
