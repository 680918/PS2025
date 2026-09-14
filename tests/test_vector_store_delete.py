from knowledge.models import EmbeddedChunk, KnowledgeChunk
from knowledge.vector_store import VectorStore


def make_embedded_chunk(document_id, chunk_index):
    chunk = KnowledgeChunk(
        document_id=document_id,
        content=f"chunk {chunk_index}",
        chunk_index=chunk_index,
        source="test.txt",
    )

    return EmbeddedChunk(
        chunk=chunk,
        vector=[1.0, 0.0, 0.0],
    )


def test_should_delete_vectors_by_document_id():
    store = VectorStore()

    item_1 = make_embedded_chunk("doc-1", 0)
    item_2 = make_embedded_chunk("doc-1", 1)
    item_3 = make_embedded_chunk("doc-2", 0)

    store.add_many([item_1, item_2, item_3])

    deleted = store.delete_by_document_id("doc-1")

    assert deleted == [item_1, item_2]
    assert store.list_all() == [item_3]


def test_should_return_empty_list_when_document_has_no_vectors():
    store = VectorStore()

    deleted = store.delete_by_document_id("missing-doc")

    assert deleted == []
