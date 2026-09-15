from knowledge.models import KnowledgeDocument
from knowledge.scope_resolver import resolve_document_scope
from knowledge.service import KnowledgeService


def test_scope_resolver_should_work_with_knowledge_service_documents():
    service = KnowledgeService()

    document_agent = KnowledgeDocument(
        id="doc-agent",
        title="AI Agent Tool Learning",
        content="Agent tools and tool calling.",
        source="agent_tool_notes.txt",
    )

    document_system = KnowledgeDocument(
        id="doc-system",
        title="System Thinking",
        content="Feedback loops and system thinking.",
        source="system_thinking.txt",
    )

    service.document_store.add(document_agent)
    service.document_store.add(document_system)

    available_documents = service.list_documents()

    document_ids = resolve_document_scope(
        "我想继续学习 agent tool",
        available_documents,
    )

    assert document_ids == ["doc-agent"]


def test_resolved_document_scope_should_limit_knowledge_search(
    tmp_path,
):
    service = KnowledgeService()

    agent_file = tmp_path / "agent_tool_notes.txt"
    agent_file.write_text(
        "Agent tool calling allows an agent to invoke external capabilities.",
        encoding="utf-8",
    )

    system_file = tmp_path / "system_thinking.txt"
    system_file.write_text(
        "System thinking studies feedback loops and system behavior.",
        encoding="utf-8",
    )

    agent_document, _ = service.add_document(agent_file)
    service.add_document(system_file)

    available_documents = service.list_documents()

    document_ids = resolve_document_scope(
        "请解释 agent tool",
        available_documents,
    )

    results = service.search(
        "tool",
        top_k=3,
        document_ids=document_ids,
    )

    assert document_ids == [agent_document.id]
    assert results
    assert all(result.chunk.document_id == agent_document.id for result in results)
