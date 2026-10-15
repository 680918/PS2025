from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def test_candidate_should_have_pending_status_by_default():

    candidate = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="完成多次学习",
        confidence=0.9,
        created_at=datetime.now(),
    )

    assert candidate.status == "PENDING"
