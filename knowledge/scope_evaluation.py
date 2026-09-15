def evaluate_document_scope(
    expected_document_ids,
    actual_document_ids,
):
    missing_document_ids = [
        document_id
        for document_id in expected_document_ids
        if document_id not in actual_document_ids
    ]

    unexpected_document_ids = [
        document_id
        for document_id in actual_document_ids
        if document_id not in expected_document_ids
    ]

    matched_document_ids = [
        document_id
        for document_id in actual_document_ids
        if document_id in expected_document_ids
    ]

    matched_count = len(matched_document_ids)

    if actual_document_ids:
        precision = matched_count / len(actual_document_ids)
    else:
        precision = 1.0 if not expected_document_ids else 0.0

    if expected_document_ids:
        recall = matched_count / len(expected_document_ids)
    else:
        recall = 1.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "passed": not missing_document_ids and not unexpected_document_ids,
        "missing_document_ids": missing_document_ids,
        "unexpected_document_ids": unexpected_document_ids,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
