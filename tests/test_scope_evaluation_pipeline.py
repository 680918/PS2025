from evaluation.scope_cases import SCOPE_EVALUATION_CASES

from knowledge.models import KnowledgeDocument
from knowledge.scope_evaluation_pipeline import (
    run_scope_evaluation_pipeline,
)


def test_scope_evaluation_pipeline_should_return_core_results(
    tmp_path,
):
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="Agent tool calling knowledge.",
            source="agent_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="System thinking knowledge.",
            source="systems.txt",
        ),
        KnowledgeDocument(
            id="doc-memory",
            title="Agent Memory",
            content="Agent memory knowledge.",
            source="memory_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Notes",
            content="General reference material.",
            source="archive_reference.txt",
        ),
    ]

    result = run_scope_evaluation_pipeline(
        cases=SCOPE_EVALUATION_CASES,
        available_documents=documents,
        output_dir=tmp_path,
    )

    assert "batch_result" in result
    assert "tuning_result" in result
    assert "report" in result


def test_scope_evaluation_pipeline_should_save_history_bundle(
    tmp_path,
):
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="Agent tool calling knowledge.",
            source="agent_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="System thinking knowledge.",
            source="systems.txt",
        ),
        KnowledgeDocument(
            id="doc-memory",
            title="Agent Memory",
            content="Agent memory knowledge.",
            source="memory_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Notes",
            content="General reference material.",
            source="archive_reference.txt",
        ),
    ]

    result = run_scope_evaluation_pipeline(
        cases=SCOPE_EVALUATION_CASES,
        available_documents=documents,
        output_dir=tmp_path,
    )

    history_paths = result["history_paths"]

    assert history_paths["txt_path"].exists()
    assert history_paths["json_path"].exists()

    assert history_paths["txt_path"].name == "scope_evaluation_001.txt"

    assert history_paths["json_path"].name == "scope_evaluation_001.json"


def test_scope_evaluation_pipeline_should_compare_with_previous_history(
    tmp_path,
):
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="Agent tool calling knowledge.",
            source="agent_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="System thinking knowledge.",
            source="systems.txt",
        ),
        KnowledgeDocument(
            id="doc-memory",
            title="Agent Memory",
            content="Agent memory knowledge.",
            source="memory_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Notes",
            content="General reference material.",
            source="archive_reference.txt",
        ),
    ]

    first_result = run_scope_evaluation_pipeline(
        cases=SCOPE_EVALUATION_CASES,
        available_documents=documents,
        output_dir=tmp_path,
    )

    assert first_result["comparison"] is None

    second_result = run_scope_evaluation_pipeline(
        cases=SCOPE_EVALUATION_CASES,
        available_documents=documents,
        output_dir=tmp_path,
    )

    comparison = second_result["comparison"]

    assert comparison is not None
    assert comparison["status"] == "unchanged"
    assert comparison["f1_delta"] == 0.0


def test_scope_evaluation_pipeline_should_save_comparison_report(
    tmp_path,
):
    documents = [
        KnowledgeDocument(
            id="doc-agent",
            title="AI Agent Tool Calling",
            content="Agent tool calling knowledge.",
            source="agent_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-system",
            title="System Thinking",
            content="System thinking knowledge.",
            source="systems.txt",
        ),
        KnowledgeDocument(
            id="doc-memory",
            title="Agent Memory",
            content="Agent memory knowledge.",
            source="memory_notes.txt",
        ),
        KnowledgeDocument(
            id="doc-general",
            title="General Notes",
            content="General reference material.",
            source="archive_reference.txt",
        ),
    ]

    run_scope_evaluation_pipeline(
        cases=SCOPE_EVALUATION_CASES,
        available_documents=documents,
        output_dir=tmp_path,
    )

    result = run_scope_evaluation_pipeline(
        cases=SCOPE_EVALUATION_CASES,
        available_documents=documents,
        output_dir=tmp_path,
    )

    comparison_path = result["comparison_path"]

    assert comparison_path is not None
    assert comparison_path.exists()

    content = comparison_path.read_text(
        encoding="utf-8",
    )

    assert "Knowledge Scope Regression Comparison" in content
    assert "Status: unchanged" in content
