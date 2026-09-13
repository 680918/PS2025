import pytest

from knowledge.embedding_retriever import (
    cosine_similarity,
)


def test_cosine_similarity_should_be_one_for_same_vector():
    score = cosine_similarity(
        [1.0, 0.0],
        [1.0, 0.0],
    )

    assert score == pytest.approx(1.0)


def test_cosine_similarity_should_be_zero_for_orthogonal_vectors():
    score = cosine_similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    )

    assert score == pytest.approx(0.0)


def test_cosine_similarity_should_reject_dimension_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity(
            [1.0, 0.0],
            [1.0],
        )

from knowledge.embedding_retriever import (
    cosine_similarity,
    retrieve_chunks_by_embedding,
)
from knowledge.models import KnowledgeChunk
from knowledge.store import KnowledgeStore


def test_embedding_retriever_should_rank_semantic_match_first():
    store = KnowledgeStore()

    store.add_many(
        [
            KnowledgeChunk(
                document_id="python",
                content="Python函数可以封装重复逻辑。",
                chunk_index=0,
                source="python.txt",
                id="function-chunk",
            ),
            KnowledgeChunk(
                document_id="python",
                content="Python变量用于保存数据。",
                chunk_index=1,
                source="python.txt",
                id="variable-chunk",
            ),
        ]
    )

    vectors = {
        "如何把重复逻辑封装起来？": [
            1.0,
            0.0,
        ],
        "Python函数可以封装重复逻辑。": [
            0.9,
            0.1,
        ],
        "Python变量用于保存数据。": [
            0.0,
            1.0,
        ],
    }

    class FakeEmbeddingProvider:
        def embed(self, text):
            return vectors[text]

    results = retrieve_chunks_by_embedding(
        "如何把重复逻辑封装起来？",
        store,
        FakeEmbeddingProvider(),
        top_k=1,
    )

    assert len(results) == 1
    assert (
        results[0].chunk.id
        == "function-chunk"
    )

def test_embedding_provider_contract():
    from knowledge.embedding_provider import (
        EmbeddingProvider,
    )

    class FakeProvider(EmbeddingProvider):
        def embed(self, text):
            return [1.0, 0.0]

    provider = FakeProvider()

    assert provider.embed("hello") == [
        1.0,
        0.0,
    ]