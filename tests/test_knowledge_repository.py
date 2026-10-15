from coach.knowledge.repository import (
    KnowledgeArtifactRepository,
)

from coach.knowledge.artifact import (
    KnowledgeArtifact,
)

from datetime import datetime


def test_repository_should_save_and_find_artifact():

    repository = KnowledgeArtifactRepository()

    artifact = KnowledgeArtifact(
        title="Memory教程",
        artifact_type="tutorial",
        topic="Memory",
        content="内容",
        source_candidate="candidate-1",
        created_at=datetime.now(),
    )

    repository.save(artifact)

    results = repository.find_by_topic("Memory")

    assert len(results) == 1

    assert results[0].title == "Memory教程"
