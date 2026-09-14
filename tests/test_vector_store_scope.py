from knowledge.models import EmbeddedChunk, KnowledgeChunk
from knowledge.vector_store import VectorStore


def make_item(document_id, chunk_index):
    chunk = KnowledgeChunk(
        document_id=document_id,
        content=f"{document_id} chunk {chunk_index}",
        chunk_index=chunk_index,
        source=f"{document_id}.txt",
    )

    return EmbeddedChunk(
        chunk=chunk,
        vector=[1.0, 0.0, 0.0],
    )


def test_should_list_vectors_for_selected_document_ids():
    store = VectorStore()

    item_1 = make_item("doc-1", 0)
    item_2 = make_item("doc-1", 1)
    item_3 = make_item("doc-2", 0)
    item_4 = make_item("doc-3", 0)

    store.add_many(
        [
            item_1,
            item_2,
            item_3,
            item_4,
        ]
    )

    result = store.list_by_document_ids(
        ["doc-1", "doc-3"],
    )

    assert result == [
        item_1,
        item_2,
        item_4,
    ]


def test_should_return_empty_list_when_no_vector_document_matches():
    store = VectorStore()

    store.add(
        make_item("doc-1", 0),
    )

    result = store.list_by_document_ids(
        ["missing-doc"],
    )

    assert result == []


def test_should_return_empty_list_when_vector_document_ids_is_empty():
    store = VectorStore()

    store.add(
        make_item("doc-1", 0),
    )

    result = store.list_by_document_ids([])

    assert result == []
