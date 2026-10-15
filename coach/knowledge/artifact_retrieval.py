class KnowledgeArtifactRetrieval:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def search(
        self,
        query,
    ):

        artifacts = self.repository.list_all()

        return [
            artifact
            for artifact in artifacts
            if query.lower() in artifact.topic.lower()
        ]
