from knowledge.models import KnowledgeChunk
from knowledge.retriever import retrieve_chunks
from knowledge.store import KnowledgeStore


def make_chunk(document_id, content, chunk_index=0):
    return KnowledgeChunk(
        document_id=document_id,
        content=content,
        chunk_index=chunk_index,
        source=f"{document_id}.txt",
    )


def test_should_retrieve_only_from_selected_documents():
    store = KnowledgeStore()

    python_chunk = make_chunk(
        "doc-python",
        "Python函数用于封装重复使用的逻辑。",
    )

    loop_chunk = make_chunk(
        "doc-loop",
        "Python循环用于重复执行一段代码。",
    )

    store.add_many(
        [
            python_chunk,
            loop_chunk,
        ]
    )

    results = retrieve_chunks(
        "Python函数",
        store,
        top_k=3,
        document_ids=["doc-loop"],
    )

    assert all(result.chunk.document_id == "doc-loop" for result in results)


def test_should_search_all_documents_when_document_ids_is_none():
    store = KnowledgeStore()

    python_chunk = make_chunk(
        "doc-python",
        "Python函数用于封装重复使用的逻辑。",
    )

    loop_chunk = make_chunk(
        "doc-loop",
        "Python循环用于重复执行一段代码。",
    )

    store.add_many(
        [
            python_chunk,
            loop_chunk,
        ]
    )

    results = retrieve_chunks(
        "Python函数",
        store,
        top_k=3,
        document_ids=None,
    )

    assert any(result.chunk.document_id == "doc-python" for result in results)


def test_should_return_empty_results_when_document_ids_is_empty():
    store = KnowledgeStore()

    store.add(
        make_chunk(
            "doc-python",
            "Python函数用于封装重复使用的逻辑。",
        )
    )

    results = retrieve_chunks(
        "Python函数",
        store,
        top_k=3,
        document_ids=[],
    )

    assert results == []
