from datetime import datetime

from coach.knowledge.artifact import (
    KnowledgeArtifact,
)

from coach.knowledge.artifact_context_builder import (
    build_artifact_context,
)


def test_context_builder_should_create_agent_context():

    artifact = KnowledgeArtifact(
        title="Memory Retrieval教程",
        artifact_type="tutorial",
        topic="Memory Retrieval",
        content="关于记忆检索的方法",
        source_candidate="candidate-001",
        created_at=datetime.now(),
    )

    context = build_artifact_context([artifact])

    assert "Memory Retrieval" in context

    assert "记忆检索" in context
