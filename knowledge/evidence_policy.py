from dataclasses import dataclass

from knowledge.hybrid_topic_resolver import (
    resolve_topics,
)
from knowledge.models import KnowledgeChunk
from knowledge.required_topic_resolver import (
    resolve_required_topics,
)


@dataclass
class EvidenceDecision:
    supported: bool
    accepted_chunks: list[KnowledgeChunk]
    reason: str


def decide_evidence(
    query,
    retrieval_results,
    embedding_provider=None,
):
    mentioned_topics = resolve_topics(
        query,
        embedding_provider=embedding_provider,
    )

    required_topics = resolve_required_topics(
        query=query,
        mentioned_topics=mentioned_topics,
        embedding_provider=embedding_provider,
    )

    if not required_topics:
        return EvidenceDecision(
            supported=False,
            accepted_chunks=[],
            reason="no supported query topic was identified",
        )

    accepted_chunks = []
    covered_topics = set()

    for result in retrieval_results:
        content = result.chunk.content

        matched_topics = [topic for topic in required_topics if topic in content]

        if matched_topics:
            accepted_chunks.append(result.chunk)

            covered_topics.update(matched_topics)

    all_topics_covered = all(topic in covered_topics for topic in required_topics)

    if all_topics_covered:
        return EvidenceDecision(
            supported=True,
            accepted_chunks=accepted_chunks,
            reason="retrieved evidence covers all query topics",
        )

    return EvidenceDecision(
        supported=False,
        accepted_chunks=[],
        reason="retrieved evidence does not cover all query topics",
    )
