from knowledge.embedding_indexer import (
    index_chunks,
)
from knowledge.models import KnowledgeChunk
from knowledge.vector_retriever import (
    retrieve_from_vector_store,
)
from knowledge.vector_store import VectorStore


class FakeEmbeddingProvider:
    def embed(self, text):
        if "函数" in text or "封装" in text:
            return [1.0, 0.0]

        if "变量" in text or "数据" in text:
            return [0.0, 1.0]

        return [0.5, 0.5]


def make_chunk(
    chunk_id,
    content,
    index,
):
    return KnowledgeChunk(
        document_id="python",
        content=content,
        chunk_index=index,
        source="python.txt",
        id=chunk_id,
    )


def build_vector_store():
    provider = FakeEmbeddingProvider()
    store = VectorStore()

    chunks = [
        make_chunk(
            "function-chunk",
            "Python函数可以封装重复逻辑。",
            0,
        ),
        make_chunk(
            "variable-chunk",
            "Python变量用于保存程序中的数据。",
            1,
        ),
    ]

    index_chunks(
        chunks,
        provider,
        store,
    )

    return provider, store


def test_vector_retriever_should_return_best_match():
    provider, store = build_vector_store()

    results = retrieve_from_vector_store(
        "如何封装重复逻辑？",
        store,
        provider,
        top_k=1,
    )

    assert len(results) == 1
    assert (
        results[0].chunk.id
        == "function-chunk"
    )


def test_vector_retriever_should_return_top_k():
    provider, store = build_vector_store()

    results = retrieve_from_vector_store(
        "Python",
        store,
        provider,
        top_k=2,
    )

    assert len(results) == 2


def test_vector_retriever_should_return_empty_for_blank_query():
    provider, store = build_vector_store()

    results = retrieve_from_vector_store(
        "",
        store,
        provider,
    )

    assert results == []