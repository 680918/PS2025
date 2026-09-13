from knowledge.models import (
    EmbeddedChunk,
    KnowledgeChunk,
)
from knowledge.vector_store import VectorStore


def make_embedded_chunk(
    chunk_id="chunk-1",
):
    chunk = KnowledgeChunk(
        document_id="doc-1",
        content="Python函数可以封装重复逻辑。",
        chunk_index=0,
        source="python.txt",
        id=chunk_id,
    )

    return EmbeddedChunk(
        chunk=chunk,
        vector=[
            0.1,
            0.2,
            0.3,
        ],
    )


def test_vector_store_should_add_item():
    store = VectorStore()

    item = make_embedded_chunk()

    store.add(item)

    assert store.list_all() == [
        item
    ]


def test_vector_store_should_add_many():
    store = VectorStore()

    item1 = make_embedded_chunk(
        "chunk-1"
    )

    item2 = make_embedded_chunk(
        "chunk-2"
    )

    store.add_many(
        [
            item1,
            item2,
        ]
    )

    assert len(store.list_all()) == 2


def test_vector_store_should_get_by_chunk_id():
    store = VectorStore()

    item = make_embedded_chunk(
        "chunk-1"
    )

    store.add(item)

    result = store.get_by_chunk_id(
        "chunk-1"
    )

    assert result == item


def test_vector_store_should_return_none_for_missing_chunk():
    store = VectorStore()

    assert (
        store.get_by_chunk_id(
            "missing"
        )
        is None
    )