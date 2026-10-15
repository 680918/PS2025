def build_knowledge_context(
    repository,
    topic=None,
):

    if repository is None:
        return {}

    artifacts = repository.list_all()

    if topic is not None:
        artifacts = [artifact for artifact in artifacts if artifact.topic == topic]

    if not artifacts:
        return {}

    return {
        "knowledge": [
            {
                "topic": artifact.topic,
                "content": artifact.content,
            }
            for artifact in artifacts
        ]
    }
