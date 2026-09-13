from knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)


def test_create_knowledge_document():
    document = KnowledgeDocument(
        title="系统之美",
        content="系统由相互连接的要素组成。",
        source="system_thinking.md",
    )

    assert document.title == "系统之美"
    assert document.content == "系统由相互连接的要素组成。"
    assert document.source == "system_thinking.md"
    assert document.id


def test_create_knowledge_chunk():
    chunk = KnowledgeChunk(
        document_id="doc-1",
        content="增强回路会强化系统原有变化。",
        chunk_index=0,
        source="system_thinking.md",
    )

    assert chunk.document_id == "doc-1"
    assert chunk.chunk_index == 0
    assert chunk.id
