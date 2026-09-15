SCOPE_EVALUATION_CASES = [
    {
        "name": "strong_agent_title_match",
        "query": "agent tool",
        "expected_document_ids": [
            "doc-agent",
        ],
    },
    {
        "name": "strong_system_title_match",
        "query": "system thinking",
        "expected_document_ids": [
            "doc-system",
        ],
    },
    {
        "name": "weak_source_only_match",
        "query": "archive",
        "expected_document_ids": [],
    },
    {
        "name": "multiple_relevant_documents",
        "query": "agent memory",
        "expected_document_ids": [
            "doc-agent",
            "doc-memory",
        ],
    },
    {
        "name": "no_relevant_document",
        "query": "quantum biology",
        "expected_document_ids": [],
    },
    {
        "name": "distractor_should_not_be_selected",
        "query": "tool calling",
        "expected_document_ids": [
            "doc-agent",
        ],
    },
]
