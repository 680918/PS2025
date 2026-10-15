from coach.knowledge.suggestion_service import (
    KnowledgeSuggestionService,
)

from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def test_service_should_create_suggestion_from_candidate():

    service = KnowledgeSuggestionService()

    candidate = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="完成多次学习",
        confidence=0.9,
        created_at=datetime.now(),
    )

    suggestion = service.create_suggestion(candidate)

    assert suggestion is not None

    assert suggestion.candidate_id == candidate.candidate_id
