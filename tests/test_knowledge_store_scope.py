from knowledge.models import KnowledgeChunk
from knowledge.store import KnowledgeStore


def make_chunk(document_id, chunk_index):
    return KnowledgeChunk(
        document_id=document_id,
        content=f"{document_id} chunk {chunk_index}",
        chunk_index=chunk_index,
        source=f"{document_id}.txt",
    )


def test_should_list_chunks_for_selected_document_ids():
    store = KnowledgeStore()

    chunk_1 = make_chunk("doc-1", 0)
    chunk_2 = make_chunk("doc-1", 1)
    chunk_3 = make_chunk("doc-2", 0)
    chunk_4 = make_chunk("doc-3", 0)

    store.add_many(
        [
            chunk_1,
            chunk_2,
            chunk_3,
            chunk_4,
        ]
    )

    result = store.list_by_document_ids(
        ["doc-1", "doc-3"],
    )

    assert result == [
        chunk_1,
        chunk_2,
        chunk_4,
    ]


def test_should_return_empty_list_when_no_document_matches():
    store = KnowledgeStore()

    store.add(
        make_chunk("doc-1", 0),
    )

    result = store.list_by_document_ids(
        ["missing-doc"],
    )

    assert result == []


def test_should_return_empty_list_when_document_ids_is_empty():
    store = KnowledgeStore()

    store.add(
        make_chunk("doc-1", 0),
    )

    result = store.list_by_document_ids([])

    assert result == []
