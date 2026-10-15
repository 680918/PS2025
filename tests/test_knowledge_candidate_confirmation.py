from coach.knowledge.confirmation import (
    confirm_candidate,
    reject_candidate,
)

from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def create_candidate():

    return KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="完成多次学习",
        confidence=0.9,
        created_at=datetime.now(),
    )


def test_confirm_candidate_should_change_status():

    candidate = create_candidate()

    confirm_candidate(candidate)

    assert candidate.status == "CONFIRMED"


def test_reject_candidate_should_change_status():

    candidate = create_candidate()

    reject_candidate(candidate)

    assert candidate.status == "REJECTED"
