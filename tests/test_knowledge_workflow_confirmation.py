from coach.knowledge.workflow import (
    KnowledgeCreationWorkflow,
)

from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from coach.knowledge.confirmation import (
    confirm_candidate,
)

from datetime import datetime


def create_candidate():

    return KnowledgeCandidate(
        topic="Memory Retrieval",
        candidate_type="tutorial",
        reason="学习完成",
        confidence=0.9,
        created_at=datetime.now(),
    )


def test_workflow_should_not_create_artifact_when_candidate_pending():

    workflow = KnowledgeCreationWorkflow()

    candidate = create_candidate()

    artifact = workflow.create_from_candidate(
        candidate,
        "教程内容",
    )

    assert artifact is None


def test_workflow_should_create_artifact_after_confirmation():

    workflow = KnowledgeCreationWorkflow()

    candidate = create_candidate()

    confirm_candidate(candidate)

    artifact = workflow.create_from_candidate(
        candidate,
        "教程内容",
    )

    assert artifact is not None
