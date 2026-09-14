from knowledge.models import (
    KnowledgeChunk,
    RetrievalResult,
)


def test_retrieval_result_should_expose_debug_metadata():
    chunk = KnowledgeChunk(
        document_id="python",
        content="Python函数可以封装重复逻辑。",
        chunk_index=0,
        source="python.txt",
        id="function-chunk",
    )

    result = RetrievalResult(
        chunk=chunk,
        score=0.82,
    )

    context = {
        "chunk_id": result.chunk.id,
        "document_id": result.chunk.document_id,
        "content": result.chunk.content,
        "source": result.chunk.source,
        "chunk_index": result.chunk.chunk_index,
        "score": result.score,
        "rank": 1,
    }

    assert context["chunk_id"] == "function-chunk"

    assert context["document_id"] == "python"

    assert context["source"] == "python.txt"

    assert context["chunk_index"] == 0

    assert context["score"] == 0.82

    assert context["rank"] == 1
