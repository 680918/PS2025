from knowledge.embedding_retriever import (
    cosine_similarity,
)
from knowledge.models import RetrievalResult


def retrieve_from_vector_store(
    query,
    vector_store,
    embedding_provider,
    top_k=3,
    min_score=0.0,
):
    if not query.strip():
        return []

    query_vector = embedding_provider.embed(
        query
    )

    scored_items = []

    for item in vector_store.list_all():
        score = cosine_similarity(
            query_vector,
            item.vector,
        )

        if score >= min_score:
            scored_items.append(
                (
                    score,
                    item,
                )
            )

    scored_items.sort(
        key=lambda pair: pair[0],
        reverse=True,
    )

    return [
        RetrievalResult(
            chunk=item.chunk,
            score=score,
        )
        for score, item in scored_items[:top_k]
    ]