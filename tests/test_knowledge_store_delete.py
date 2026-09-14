from knowledge.models import KnowledgeChunk
from knowledge.store import KnowledgeStore


def make_chunk(document_id, chunk_index):
    return KnowledgeChunk(
        document_id=document_id,
        content=f"chunk {chunk_index}",
        chunk_index=chunk_index,
        source="test.txt",
    )


def test_should_delete_chunks_by_document_id():
    store = KnowledgeStore()

    chunk_1 = make_chunk("doc-1", 0)
    chunk_2 = make_chunk("doc-1", 1)
    chunk_3 = make_chunk("doc-2", 0)

    store.add_many([chunk_1, chunk_2, chunk_3])

    deleted = store.delete_by_document_id("doc-1")

    assert deleted == [chunk_1, chunk_2]
    assert store.list_all() == [chunk_3]


def test_should_return_empty_list_when_document_has_no_chunks():
    store = KnowledgeStore()

    deleted = store.delete_by_document_id("missing-doc")

    assert deleted == []
