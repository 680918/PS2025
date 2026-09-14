from knowledge.question_mode_resolver import (
    resolve_question_mode,
)

from knowledge.semantic_required_topic_resolver import (
    REQUIRED_TOPIC_PROTOTYPES,
    resolve_semantic_required_topics,
)


def resolve_required_topics(
    query,
    mentioned_topics,
    embedding_provider=None,
):
    if not mentioned_topics:
        return []

    question_mode = resolve_question_mode(query)

    if question_mode == "comparison":
        return mentioned_topics

    explicit_topics = [topic for topic in mentioned_topics if topic in query]

    if len(explicit_topics) == 1:
        return explicit_topics

    if embedding_provider is not None:
        candidate_topics = list(
            dict.fromkeys(
                [
                    *mentioned_topics,
                    *REQUIRED_TOPIC_PROTOTYPES.keys(),
                ]
            )
        )

        return resolve_semantic_required_topics(
            query=query,
            mentioned_topics=candidate_topics,
            embedding_provider=embedding_provider,
        )

    return mentioned_topics
