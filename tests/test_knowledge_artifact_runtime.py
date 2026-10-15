from datetime import datetime


from coach.knowledge.artifact import (
    KnowledgeArtifact,
)

from coach.knowledge.repository import (
    KnowledgeArtifactRepository,
)

from coach.knowledge.artifact_runtime import (
    KnowledgeArtifactRuntimeService,
)


def test_runtime_should_return_personal_knowledge_context():

    repository = KnowledgeArtifactRepository()

    repository.save(
        KnowledgeArtifact(
            title="Memory Retrieval教程",
            artifact_type="tutorial",
            topic="Memory Retrieval",
            content="关于记忆检索的方法",
            source_candidate="candidate-001",
            created_at=datetime.now(),
        )
    )

    service = KnowledgeArtifactRuntimeService(repository)

    context = service.retrieve("Memory Retrieval")

    assert "Memory Retrieval" in context
