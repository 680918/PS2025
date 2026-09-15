from knowledge.models import KnowledgeDocument
from knowledge.scope_tuning import tune_scope_parameters
from evaluation.scope_cases import SCOPE_EVALUATION_CASES


def test_scope_tuning_should_select_best_parameter_combination():
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

    result = tune_scope_parameters(
        cases=cases,
        available_documents=documents,
        top_n_values=[1, 2],
        min_score_values=[1, 2],
    )

    assert result["best_parameters"] is not None

    assert result["best_parameters"]["top_n"] in [1, 2]
    assert result["best_parameters"]["min_score"] in [1, 2]

    assert result["best_score"] == 1.0

    assert len(result["trials"]) == 4


def test_scope_tuning_should_choose_best_parameters_with_tie_breaking():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool",
            content="...",
            source="notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Notes",
            content="...",
            source="tool_reference.txt",
        ),
    ]

    cases = [
        {
            "query": "agent tool",
            "expected_document_ids": ["doc-agent"],
        },
    ]

    result = tune_scope_parameters(
        cases=cases,
        available_documents=documents,
        top_n_values=[1, 2],
        min_score_values=[1, 2],
    )

    assert result["best_score"] == 1.0

    assert result["best_parameters"] == {
        "top_n": 1,
        "min_score": 2,
    }


def test_scope_tuning_should_prefer_smaller_top_n_when_scores_tie():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool",
            content="...",
            source="notes.txt",
        ),
    ]

    cases = [
        {
            "query": "agent tool",
            "expected_document_ids": ["doc-agent"],
        },
    ]

    result = tune_scope_parameters(
        cases=cases,
        available_documents=documents,
        top_n_values=[2, 1],
        min_score_values=[1],
    )

    assert result["best_score"] == 1.0

    assert result["best_parameters"] == {
        "top_n": 1,
        "min_score": 1,
    }


def test_scope_tuning_should_prefer_higher_min_score_when_top_n_and_score_tie():
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool",
            content="...",
            source="notes.txt",
        ),
    ]

    cases = [
        {
            "query": "agent tool",
            "expected_document_ids": ["doc-agent"],
        },
    ]

    result = tune_scope_parameters(
        cases=cases,
        available_documents=documents,
        top_n_values=[1],
        min_score_values=[1, 2],
    )

    assert result["best_score"] == 1.0

    assert result["best_parameters"] == {
        "top_n": 1,
        "min_score": 2,
    }
