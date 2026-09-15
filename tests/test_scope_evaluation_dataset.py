from evaluation.scope_cases import SCOPE_EVALUATION_CASES


def test_scope_evaluation_dataset_should_not_be_empty():
    assert SCOPE_EVALUATION_CASES


def test_scope_evaluation_dataset_cases_should_have_required_fields():
    for case in SCOPE_EVALUATION_CASES:
        assert "query" in case
        assert "expected_document_ids" in case


def test_scope_evaluation_dataset_queries_should_not_be_empty():
    for case in SCOPE_EVALUATION_CASES:
        assert case["query"]


def test_scope_evaluation_dataset_expected_ids_should_be_lists():
    for case in SCOPE_EVALUATION_CASES:
        assert isinstance(
            case["expected_document_ids"],
            list,
        )
