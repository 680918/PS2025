class KnowledgeArtifactRepository:
    def __init__(self):

        self.artifacts = []

    def save(
        self,
        artifact,
    ):

        self.artifacts.append(artifact)

    def list_all(
        self,
    ):

        return self.artifacts

    def find_by_topic(
        self,
        topic,
    ):

        return [artifact for artifact in self.artifacts if artifact.topic == topic]
