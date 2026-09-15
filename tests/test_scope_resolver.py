from knowledge.models import KnowledgeDocument
from knowledge.scope_resolver import (
    resolve_document_scope,
    resolve_document_scope_with_trace,
)


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


def test_scope_resolver_should_rank_more_relevant_document_first():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="...",
            source="agent_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Learning Notes",
            content="...",
            source="tool_reference.txt",
        ),
    ]

    result = resolve_document_scope(
        "agent tool",
        documents,
    )

    assert result == [
        "doc-agent",
        "doc-general",
    ]


def test_scope_resolver_should_rank_by_relevance_not_input_order():
    documents = [
        KnowledgeDocument(
            id="doc-general",
            title="General Learning Notes",
            content="...",
            source="tool_reference.txt",
        ),
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="...",
            source="agent_notes.txt",
        ),
    ]

    result = resolve_document_scope(
        "agent tool",
        documents,
    )

    assert result == [
        "doc-agent",
        "doc-general",
    ]


def test_scope_resolver_should_limit_results_with_top_n():
    documents = [
        KnowledgeDocument(
            id="doc-general",
            title="General Tool Notes",
            content="...",
            source="tool_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="...",
            source="agent_tool_notes.txt",
        ),
    ]

    result = resolve_document_scope(
        "agent tool",
        documents,
        top_n=1,
    )

    assert result == ["doc-agent"]


def test_scope_resolver_should_return_all_matches_when_top_n_is_none():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool",
            content="...",
            source="agent_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="Tool Reference",
            content="...",
            source="tool_reference.txt",
        ),
    ]

    result = resolve_document_scope(
        "agent tool",
        documents,
        top_n=None,
    )

    assert result == [
        "doc-agent",
        "doc-general",
    ]


def test_scope_resolver_should_filter_documents_below_min_score():
    documents = [
        KnowledgeDocument(
            id="doc-strong",
            title="AI Agent Tool Calling",
            content="...",
            source="agent_tool_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-weak",
            title="General Notes",
            content="...",
            source="tool.txt",
        ),
    ]

    result = resolve_document_scope(
        "agent tool",
        documents,
        min_score=3,
    )

    assert result == ["doc-strong"]


def test_scope_resolver_should_return_none_when_all_scores_are_below_threshold():
    documents = [
        KnowledgeDocument(
            id="doc-weak",
            title="General Notes",
            content="...",
            source="tool.txt",
        ),
    ]

    result = resolve_document_scope(
        "agent tool",
        documents,
        min_score=3,
    )

    assert result is None


def test_scope_resolver_trace_should_explain_selected_and_rejected_documents():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="...",
            source="learning_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Notes",
            content="...",
            source="tool_reference.txt",
        ),
    ]

    result = resolve_document_scope_with_trace(
        "agent tool",
        documents,
        top_n=3,
        min_score=2,
    )

    assert result["selected_document_ids"] == [
        "doc-agent",
    ]

    assert result["candidates"][0] == {
        "document_id": "doc-agent",
        "score": 4,
        "selected": True,
        "matched_title_terms": [
            "agent",
            "tool",
        ],
        "matched_source_terms": [],
        "reason": "selected",
    }

    assert result["candidates"][1] == {
        "document_id": "doc-general",
        "score": 1,
        "selected": False,
        "matched_title_terms": [],
        "matched_source_terms": [
            "tool",
        ],
        "reason": "below_min_score",
    }


def test_scope_resolver_trace_should_explain_top_n_exclusion():
    documents = [
        KnowledgeDocument(
            id="doc-1",
            title="AI Agent Tool",
            content="...",
            source="learning_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-2",
            title="Agent Learning",
            content="...",
            source="tool_reference.txt",
        ),
    ]

    result = resolve_document_scope_with_trace(
        "agent tool",
        documents,
        top_n=1,
        min_score=1,
    )

    assert result["selected_document_ids"] == ["doc-1"]

    assert result["candidates"][0]["document_id"] == "doc-1"
    assert result["candidates"][0]["reason"] == "selected"

    assert result["candidates"][1]["document_id"] == "doc-2"
    assert result["candidates"][1]["selected"] is False
    assert result["candidates"][1]["reason"] == "excluded_by_top_n"
