from knowledge.scope_resolver import resolve_document_scope
from knowledge.models import KnowledgeDocument


def test_scope_resolver_should_return_none_when_user_message_is_empty():
    result = resolve_document_scope(
        "",
        [
            {
                "id": "doc-agent",
                "title": "AI Agent",
                "tags": ["agent"],
            }
        ],
    )

    assert result is None


def test_scope_resolver_should_return_none_when_no_documents():
    result = resolve_document_scope(
        "Tool Calling 是什么？",
        [],
    )

    assert result is None


def test_scope_resolver_should_match_document_by_tag():
    result = resolve_document_scope(
        "我想继续学习 tool calling",
        [
            {
                "id": "doc-agent",
                "title": "AI Agent 学习笔记",
                "tags": ["agent", "tool", "memory"],
            },
            {
                "id": "doc-system",
                "title": "系统之美",
                "tags": ["系统思维", "反馈回路"],
            },
        ],
    )

    assert result == ["doc-agent"]


def test_scope_resolver_should_match_multiple_documents():
    result = resolve_document_scope(
        "我想学习 agent 和 系统思维",
        [
            {
                "id": "doc-agent",
                "title": "AI Agent 学习笔记",
                "tags": ["agent", "tool"],
            },
            {
                "id": "doc-system",
                "title": "系统之美",
                "tags": ["系统思维", "反馈回路"],
            },
        ],
    )

    assert result == [
        "doc-agent",
        "doc-system",
    ]


def test_scope_resolver_should_return_none_when_no_tag_matches():
    result = resolve_document_scope(
        "今天想学习财务分析",
        [
            {
                "id": "doc-agent",
                "title": "AI Agent 学习笔记",
                "tags": ["agent", "tool"],
            }
        ],
    )

    assert result is None


def test_scope_resolver_should_match_tags_case_insensitively():
    result = resolve_document_scope(
        "Tell me about TOOL calling",
        [
            {
                "id": "doc-agent",
                "title": "AI Agent 学习笔记",
                "tags": ["tool"],
            }
        ],
    )

    assert result == ["doc-agent"]


def test_scope_resolver_should_not_duplicate_document_id_when_multiple_tags_match():
    result = resolve_document_scope(
        "agent tool memory",
        [
            {
                "id": "doc-agent",
                "title": "AI Agent 学习笔记",
                "tags": ["agent", "tool", "memory"],
            }
        ],
    )

    assert result == ["doc-agent"]


def test_scope_resolver_should_accept_real_knowledge_documents():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Learning",
            content="...",
            source="agent_tool_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="...",
            source="system_thinking.txt",
        ),
    ]

    result = resolve_document_scope(
        "我想继续学习 agent tool",
        documents,
    )

    assert result == ["doc-agent"]
