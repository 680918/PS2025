from datetime import datetime

from coach.knowledge.artifact import (
    KnowledgeArtifact,
)

from coach.knowledge.artifact_ranker import (
    rank_artifacts,
)


def test_ranker_should_put_relevant_artifact_first():

    artifacts = [
        KnowledgeArtifact(
            title="Memory Retrieval教程",
            artifact_type="tutorial",
            topic="Memory Retrieval",
            content="学习记忆检索",
            source_candidate="1",
            created_at=datetime.now(),
        ),
        KnowledgeArtifact(
            title="Python基础教程",
            artifact_type="tutorial",
            topic="Python",
            content="Python基础",
            source_candidate="2",
            created_at=datetime.now(),
        ),
    ]

    ranked = rank_artifacts(
        artifacts,
        "Memory Retrieval",
    )

    assert ranked[0].topic == "Memory Retrieval"
