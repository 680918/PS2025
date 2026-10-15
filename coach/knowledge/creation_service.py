from coach.knowledge.intent import (
    is_knowledge_creation_request,
)

from coach.knowledge.workflow import (
    KnowledgeCreationWorkflow,
)


class KnowledgeCreationService:
    def __init__(
        self,
        workflow=None,
    ):

        self.workflow = workflow or KnowledgeCreationWorkflow()

    def create_from_request(
        self,
        user_message,
        candidate,
        content,
    ):

        if not is_knowledge_creation_request(user_message):
            return None

        return self.workflow.create_from_candidate(
            candidate,
            content,
        )
