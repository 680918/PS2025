from coach.knowledge.generator import (
    KnowledgeArtifactGenerator,
)

from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def test_generator_should_create_artifact_from_candidate():

    candidate = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="连续学习",
        confidence=0.9,
        created_at=datetime.now(),
    )

    generator = KnowledgeArtifactGenerator()

    artifact = generator.generate(
        candidate,
        "教程内容",
    )

    assert artifact.topic == "Memory Retrieval"

    assert artifact.content == "教程内容"

    assert artifact.artifact_type == "tutorial"

    assert artifact.source_candidate == candidate.candidate_id
