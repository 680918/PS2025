from coach.knowledge.creation_service import (
    KnowledgeCreationService,
)

from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def test_creation_service_should_create_artifact_from_user_request():

    service = KnowledgeCreationService()

    candidate = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="学习完成",
        confidence=0.9,
        created_at=datetime.now(),
    )

    candidate.status = "CONFIRMED"

    artifact = service.create_from_request(
        "把刚才学习内容整理成教程",
        candidate,
        "教程内容",
    )

    assert artifact is not None

    assert artifact.topic == "Memory Retrieval"
