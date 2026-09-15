from knowledge.scope_evaluation import evaluate_document_scope
from knowledge.scope_resolver import resolve_document_scope


def evaluate_scope_cases(
    cases,
    available_documents,
    top_n=None,
    min_score=1,
    min_relative_score=None,
):
    results = []

    for case in cases:
        query = case["query"]
        expected_document_ids = case["expected_document_ids"]

        actual_document_ids = resolve_document_scope(
            query,
            available_documents,
            top_n=top_n,
            min_score=min_score,
            min_relative_score=min_relative_score,
        )

        if actual_document_ids is None:
            actual_document_ids = []

        evaluation = evaluate_document_scope(
            expected_document_ids=expected_document_ids,
            actual_document_ids=actual_document_ids,
        )

        results.append(
            {
                "name": case.get("name"),
                "query": query,
                "expected_document_ids": expected_document_ids,
                "actual_document_ids": actual_document_ids,
                **evaluation,
            }
        )

    case_count = len(results)

    passed_count = sum(1 for result in results if result["passed"])

    if case_count == 0:
        average_precision = 1.0
        average_recall = 1.0
        average_f1 = 1.0
    else:
        average_precision = sum(result["precision"] for result in results) / case_count

        average_recall = sum(result["recall"] for result in results) / case_count

        average_f1 = sum(result["f1"] for result in results) / case_count

    return {
        "case_count": case_count,
        "passed_count": passed_count,
        "average_precision": average_precision,
        "average_recall": average_recall,
        "average_f1": average_f1,
        "results": results,
    }
