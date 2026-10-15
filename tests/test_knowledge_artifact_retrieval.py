from datetime import datetime

from coach.knowledge.artifact import (
    KnowledgeArtifact,
)

from coach.knowledge.repository import (
    KnowledgeArtifactRepository,
)

from coach.knowledge.artifact_retrieval import (
    KnowledgeArtifactRetrieval,
)


def test_retrieval_should_find_artifact_by_topic():

    repository = KnowledgeArtifactRepository()

    artifact = KnowledgeArtifact(
        title="Memory Retrieval 学习教程",
        artifact_type="tutorial",
        topic="Memory Retrieval",
        content="关于Memory Retrieval的学习总结",
        source_candidate="candidate-001",
        created_at=datetime.now(),
    )

    repository.save(artifact)

    retrieval = KnowledgeArtifactRetrieval(repository)

    results = retrieval.search("Memory Retrieval")

    assert len(results) == 1

    assert results[0].topic == "Memory Retrieval"
