from knowledge.models import KnowledgeDocument
from knowledge.scope_batch_evaluation import evaluate_scope_cases
from evaluation.scope_cases import SCOPE_EVALUATION_CASES


def test_scope_batch_evaluation_should_aggregate_multiple_cases():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool",
            content="...",
            source="notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="...",
            source="systems.txt",
        ),
    ]

    cases = SCOPE_EVALUATION_CASES

    result = evaluate_scope_cases(
        cases,
        documents,
        top_n=1,
        min_score=2,
    )

    assert result["case_count"] == 2
    assert result["passed_count"] == 2
    assert result["average_precision"] == 1.0
    assert result["average_recall"] == 1.0
    assert result["average_f1"] == 1.0
    assert len(result["results"]) == 2


def test_scope_batch_evaluation_should_aggregate_partial_failures():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool",
            content="...",
            source="notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="...",
            source="systems.txt",
        ),
    ]

    cases = [
        {
            "query": "agent tool",
            "expected_document_ids": ["doc-agent"],
        },
        {
            "query": "unknown topic",
            "expected_document_ids": ["doc-system"],
        },
    ]

    result = evaluate_scope_cases(
        cases,
        documents,
        top_n=1,
        min_score=2,
    )

    assert result["case_count"] == 2
    assert result["passed_count"] == 1

    assert result["average_precision"] == 0.5
    assert result["average_recall"] == 0.5
    assert result["average_f1"] == 0.5


def test_scope_batch_evaluation_should_handle_empty_cases():
    result = evaluate_scope_cases(
        [],
        [],
        top_n=1,
        min_score=2,
    )

    assert result["case_count"] == 0
    assert result["passed_count"] == 0
    assert result["average_precision"] == 1.0
    assert result["average_recall"] == 1.0
    assert result["average_f1"] == 1.0
    assert result["results"] == []
