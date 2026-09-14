from knowledge.models import EmbeddedChunk, KnowledgeChunk
from knowledge.vector_retriever import retrieve_from_vector_store
from knowledge.vector_store import VectorStore


class FakeEmbeddingProvider:
    def embed(self, text):
        if "函数" in text:
            return [1.0, 0.0]

        if "循环" in text:
            return [0.0, 1.0]

        return [0.5, 0.5]


def make_item(
    document_id,
    content,
    vector,
):
    chunk = KnowledgeChunk(
        document_id=document_id,
        content=content,
        chunk_index=0,
        source=f"{document_id}.txt",
    )

    return EmbeddedChunk(
        chunk=chunk,
        vector=vector,
    )


def test_should_retrieve_only_from_selected_vector_documents():
    store = VectorStore()

    function_item = make_item(
        "doc-function",
        "Python函数用于封装重复使用的逻辑。",
        [1.0, 0.0],
    )

    loop_item = make_item(
        "doc-loop",
        "Python循环用于重复执行代码。",
        [0.0, 1.0],
    )

    store.add_many(
        [
            function_item,
            loop_item,
        ]
    )

    results = retrieve_from_vector_store(
        "Python函数",
        store,
        FakeEmbeddingProvider(),
        top_k=3,
        document_ids=["doc-loop"],
    )

    assert all(result.chunk.document_id == "doc-loop" for result in results)


def test_should_search_all_vectors_when_document_ids_is_none():
    store = VectorStore()

    function_item = make_item(
        "doc-function",
        "Python函数用于封装重复使用的逻辑。",
        [1.0, 0.0],
    )

    loop_item = make_item(
        "doc-loop",
        "Python循环用于重复执行代码。",
        [0.0, 1.0],
    )

    store.add_many(
        [
            function_item,
            loop_item,
        ]
    )

    results = retrieve_from_vector_store(
        "Python函数",
        store,
        FakeEmbeddingProvider(),
        top_k=3,
        document_ids=None,
    )

    assert results[0].chunk.document_id == "doc-function"


def test_should_return_empty_results_when_vector_document_ids_is_empty():
    store = VectorStore()

    store.add(
        make_item(
            "doc-function",
            "Python函数用于封装重复使用的逻辑。",
            [1.0, 0.0],
        )
    )

    results = retrieve_from_vector_store(
        "Python函数",
        store,
        FakeEmbeddingProvider(),
        top_k=3,
        document_ids=[],
    )

    assert results == []
