from coach.knowledge.repository import (
    KnowledgeArtifactRepository,
)
from coach.knowledge.generator import (
    KnowledgeArtifactGenerator,
)


class KnowledgeCreationWorkflow:
    def __init__(
        self,
        generator=None,
        repository=None,
    ):

        self.generator = generator or KnowledgeArtifactGenerator()

        self.repository = repository or KnowledgeArtifactRepository()

    def create_from_candidate(
        self,
        candidate,
        content,
    ):

        if candidate.status != "CONFIRMED":
            return None

        artifact = self.generator.generate(
            candidate,
            content,
        )

        self.repository.save(artifact)

        return artifact
