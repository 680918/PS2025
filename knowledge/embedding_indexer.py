from knowledge.models import EmbeddedChunk


def index_chunk(
    chunk,
    embedding_provider,
    vector_store,
):
    vector = embedding_provider.embed(chunk.content)

    item = EmbeddedChunk(
        chunk=chunk,
        vector=vector,
    )

    vector_store.add(item)

    return item


def index_chunks(
    chunks,
    embedding_provider,
    vector_store,
):
    items = []

    for chunk in chunks:
        item = index_chunk(
            chunk,
            embedding_provider,
            vector_store,
        )

        items.append(item)

    return items
