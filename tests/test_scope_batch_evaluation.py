from knowledge.models import KnowledgeDocument
from knowledge.scope_batch_evaluation import evaluate_scope_cases
from evaluation.scope_cases import SCOPE_EVALUATION_CASES


def test_scope_batch_evaluation_should_aggregate_multiple_cases():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="...",
            source="agent_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="...",
            source="systems.txt",
        ),
        KnowledgeDocument(
            id="doc-memory",
            title="Agent Memory",
            content="...",
            source="memory_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Notes",
            content="...",
            source="archive_reference.txt",
        ),
    ]

    result = evaluate_scope_cases(
        SCOPE_EVALUATION_CASES,
        documents,
        top_n=2,
        min_score=2,
        min_relative_score=0.75,
    )

    for case_result in result["results"]:
        print(
            "\nCASE:",
            case_result["name"],
            "\nexpected:",
            case_result["expected_document_ids"],
            "\nactual:",
            case_result["actual_document_ids"],
            "\npassed:",
            case_result["passed"],
            "\nprecision:",
            case_result["precision"],
            "\nrecall:",
            case_result["recall"],
            "\nf1:",
            case_result["f1"],
        )

    print(
        "\nSUMMARY:",
        "\ncase_count:",
        result["case_count"],
        "\npassed_count:",
        result["passed_count"],
        "\naverage_precision:",
        result["average_precision"],
        "\naverage_recall:",
        result["average_recall"],
        "\naverage_f1:",
        result["average_f1"],
    )

    assert result["case_count"] == len(SCOPE_EVALUATION_CASES)
    assert result["passed_count"] <= result["case_count"]
    assert len(result["results"]) == len(SCOPE_EVALUATION_CASES)

    assert result["results"][0]["name"] == "strong_agent_title_match"
    assert result["results"][1]["name"] == "strong_system_title_match"


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
