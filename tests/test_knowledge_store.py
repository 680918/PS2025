from knowledge.models import KnowledgeChunk
from knowledge.store import KnowledgeStore


def make_chunk(
    document_id,
    content,
    chunk_index,
):
    return KnowledgeChunk(
        document_id=document_id,
        content=content,
        chunk_index=chunk_index,
        source="test.txt",
    )


def test_add_chunk():
    store = KnowledgeStore()

    chunk = make_chunk(
        "doc-1",
        "第一段",
        0,
    )

    result = store.add(chunk)

    assert result == chunk
    assert store.list_all() == [chunk]


def test_add_many_chunks():
    store = KnowledgeStore()

    chunk1 = make_chunk(
        "doc-1",
        "第一段",
        0,
    )

    chunk2 = make_chunk(
        "doc-1",
        "第二段",
        1,
    )

    store.add_many([chunk1, chunk2])

    assert len(store.list_all()) == 2


def test_get_chunks_by_document_id():
    store = KnowledgeStore()

    chunk1 = make_chunk(
        "doc-1",
        "第一段",
        0,
    )

    chunk2 = make_chunk(
        "doc-2",
        "第二段",
        0,
    )

    store.add_many([chunk1, chunk2])

    result = store.get_by_document_id("doc-1")

    assert len(result) == 1
    assert result[0].document_id == "doc-1"


def test_get_chunk_by_id():
    store = KnowledgeStore()

    chunk = make_chunk(
        "doc-1",
        "第一段",
        0,
    )

    store.add(chunk)

    result = store.get_by_id(chunk.id)

    assert result == chunk


def test_get_missing_chunk_returns_none():
    store = KnowledgeStore()

    result = store.get_by_id("missing")

    assert result is None