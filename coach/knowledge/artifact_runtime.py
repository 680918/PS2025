from coach.knowledge.artifact_retrieval import (
    KnowledgeArtifactRetrieval,
)

from coach.knowledge.artifact_ranker import (
    rank_artifacts,
)

from coach.knowledge.artifact_context_builder import (
    build_artifact_context,
)


class KnowledgeArtifactRuntimeService:
    def __init__(
        self,
        repository,
    ):

        self.retrieval = KnowledgeArtifactRetrieval(repository)

    def retrieve(
        self,
        query,
    ):

        artifacts = self.retrieval.search(query)

        ranked_artifacts = rank_artifacts(
            artifacts,
            query,
        )

        return build_artifact_context(ranked_artifacts)
