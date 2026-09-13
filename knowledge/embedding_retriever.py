import math

from knowledge.models import RetrievalResult


def cosine_similarity(a, b):
    if len(a) != len(b):
        raise ValueError("向量维度必须一致")

    dot_product = sum(x * y for x, y in zip(a, b))

    norm_a = math.sqrt(sum(x * x for x in a))

    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def retrieve_chunks_by_embedding(
    query,
    store,
    embedding_provider,
    top_k=3,
    min_score=0.0,
):
    if not query.strip():
        return []

    query_vector = embedding_provider.embed(query)

    scored_chunks = []

    for chunk in store.list_all():
        chunk_vector = embedding_provider.embed(chunk.content)

        score = cosine_similarity(
            query_vector,
            chunk_vector,
        )

        if score >= min_score:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        RetrievalResult(
            chunk=chunk,
            score=score,
        )
        for score, chunk in scored_chunks[:top_k]
    ]
