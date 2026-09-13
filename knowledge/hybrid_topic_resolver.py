from knowledge.semantic_topic_resolver import (
    resolve_semantic_topics,
)
from knowledge.topic_resolver import (
    resolve_query_topics,
)


def resolve_topics(
    query,
    embedding_provider=None,
):
    rule_topics = resolve_query_topics(query)

    if rule_topics:
        return rule_topics

    if embedding_provider is None:
        return []

    semantic_matches = resolve_semantic_topics(
        query=query,
        embedding_provider=embedding_provider,
    )

    return [match.topic for match in semantic_matches]
