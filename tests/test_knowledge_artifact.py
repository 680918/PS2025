from coach.knowledge.artifact import (
    KnowledgeArtifact,
)

from datetime import datetime


def test_knowledge_artifact_should_store_asset_information():

    artifact = KnowledgeArtifact(
        title="Context Intelligence教程",
        artifact_type="tutorial",
        topic="Context Intelligence",
        content="教程内容",
        source_candidate="candidate-001",
        created_at=datetime.now(),
    )

    assert artifact.title == "Context Intelligence教程"

    assert artifact.artifact_type == "tutorial"

    assert artifact.source_candidate == "candidate-001"
