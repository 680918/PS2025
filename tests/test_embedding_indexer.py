from knowledge.embedding_indexer import (
    index_chunk,
    index_chunks,
)
from knowledge.models import KnowledgeChunk
from knowledge.vector_store import VectorStore


class FakeEmbeddingProvider:
    def embed(self, text):
        if "函数" in text:
            return [1.0, 0.0]

        return [0.0, 1.0]


def make_chunk(
    chunk_id,
    content,
):
    return KnowledgeChunk(
        document_id="python",
        content=content,
        chunk_index=0,
        source="python.txt",
        id=chunk_id,
    )


def test_index_chunk_should_create_embedded_chunk():
    provider = FakeEmbeddingProvider()
    store = VectorStore()

    chunk = make_chunk(
        "function-chunk",
        "Python函数可以封装重复逻辑。",
    )

    item = index_chunk(
        chunk,
        provider,
        store,
    )

    assert item.chunk == chunk
    assert item.vector == [1.0, 0.0]


def test_index_chunk_should_save_to_vector_store():
    provider = FakeEmbeddingProvider()
    store = VectorStore()

    chunk = make_chunk(
        "function-chunk",
        "Python函数可以封装重复逻辑。",
    )

    index_chunk(
        chunk,
        provider,
        store,
    )

    saved = store.get_by_chunk_id(
        "function-chunk"
    )

    assert saved is not None
    assert saved.vector == [1.0, 0.0]


def test_index_chunks_should_index_multiple_chunks():
    provider = FakeEmbeddingProvider()
    store = VectorStore()

    chunks = [
        make_chunk(
            "function-chunk",
            "Python函数可以封装重复逻辑。",
        ),
        make_chunk(
            "variable-chunk",
            "Python变量用于保存数据。",
        ),
    ]

    items = index_chunks(
        chunks,
        provider,
        store,
    )

    assert len(items) == 2
    assert len(store.list_all()) == 2