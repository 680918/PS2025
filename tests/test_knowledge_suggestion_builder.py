from coach.knowledge.suggestion_builder import (
    build_knowledge_suggestion,
)

from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def test_builder_should_create_suggestion_from_candidate():

    candidate = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="完成多次学习",
        confidence=0.9,
        created_at=datetime.now(),
    )

    suggestion = build_knowledge_suggestion(candidate)

    assert suggestion.candidate_id == candidate.candidate_id

    assert "Memory Retrieval" in suggestion.message

    assert suggestion.status == "PENDING"
