from knowledge.scope_evaluation import evaluate_document_scope


def test_scope_evaluation_should_pass_when_actual_matches_expected():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent"],
        actual_document_ids=["doc-agent"],
    )

    assert result["passed"] is True


def test_scope_evaluation_should_fail_when_actual_differs_from_expected():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent"],
        actual_document_ids=["doc-general"],
    )

    assert result["passed"] is False


def test_scope_evaluation_should_report_missing_documents():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent", "doc-tool"],
        actual_document_ids=["doc-agent"],
    )

    assert result["passed"] is False
    assert result["missing_document_ids"] == ["doc-tool"]
    assert result["unexpected_document_ids"] == []


def test_scope_evaluation_should_report_unexpected_documents():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent"],
        actual_document_ids=["doc-agent", "doc-general"],
    )

    assert result["passed"] is False
    assert result["missing_document_ids"] == []
    assert result["unexpected_document_ids"] == ["doc-general"]


def test_scope_evaluation_should_calculate_precision_and_recall():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent", "doc-tool"],
        actual_document_ids=["doc-agent", "doc-general"],
    )

    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_scope_evaluation_should_handle_empty_actual_documents():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent"],
        actual_document_ids=[],
    )

    assert result["precision"] == 0.0
    assert result["recall"] == 0.0


def test_scope_evaluation_should_handle_both_empty_documents():
    result = evaluate_document_scope(
        expected_document_ids=[],
        actual_document_ids=[],
    )

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0


def test_scope_evaluation_should_calculate_f1_score():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent", "doc-tool"],
        actual_document_ids=["doc-agent", "doc-general"],
    )

    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5


def test_scope_evaluation_should_return_zero_f1_when_precision_and_recall_are_zero():
    result = evaluate_document_scope(
        expected_document_ids=["doc-agent"],
        actual_document_ids=[],
    )

    assert result["f1"] == 0.0


def test_scope_evaluation_should_return_one_f1_when_both_sets_are_empty():
    result = evaluate_document_scope(
        expected_document_ids=[],
        actual_document_ids=[],
    )

    assert result["f1"] == 1.0
