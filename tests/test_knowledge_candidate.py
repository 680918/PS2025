from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def test_knowledge_candidate_should_store_candidate_information():

    candidate = KnowledgeCandidate(
        topic="Context Intelligence",
        candidate_type="tutorial",
        reason="连续学习并完成实践",
        confidence=0.9,
        created_at=datetime.now(),
    )

    assert candidate.topic == "Context Intelligence"

    assert candidate.candidate_type == "tutorial"

    assert candidate.confidence == 0.9
