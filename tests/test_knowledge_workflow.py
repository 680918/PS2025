from coach.knowledge.workflow import (
    KnowledgeCreationWorkflow,
)

from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from datetime import datetime


def test_workflow_should_create_artifact_from_candidate():

    workflow = KnowledgeCreationWorkflow()

    candidate = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="学习完成",
        confidence=0.9,
        created_at=datetime.now(),
    )

    candidate.status = "CONFIRMED"

    artifact = workflow.create_from_candidate(
        candidate,
        "教程内容",
    )

    assert artifact.topic == ("Memory Retrieval")

    assert artifact.content == ("教程内容")


def test_workflow_should_save_generated_artifact():

    workflow = KnowledgeCreationWorkflow()

    candidate = KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="学习完成",
        confidence=0.9,
        created_at=datetime.now(),
    )

    candidate.status = "CONFIRMED"

    workflow.create_from_candidate(
        candidate,
        "教程内容",
    )

    artifacts = workflow.repository.list_all()

    assert len(artifacts) == 1

    assert artifacts[0].topic == "Memory Retrieval"
