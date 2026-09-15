def resolve_document_scope(
    user_message,
    available_documents,
):
    if not user_message:
        return None

    if not available_documents:
        return None

    normalized_message = user_message.lower()

    matched_document_ids = []

    for document in available_documents:
        # 兼容当前测试中的 dict
        if isinstance(document, dict):
            document_id = document["id"]
            tags = document.get("tags", [])

            if any(tag.lower() in normalized_message for tag in tags):
                matched_document_ids.append(document_id)

            continue

        # 真实系统中的 KnowledgeDocument
        document_id = document.id

        searchable_text = " ".join(
            [
                document.title,
                document.source,
            ]
        ).lower()

        words = normalized_message.split()

        if any(word in searchable_text for word in words):
            matched_document_ids.append(document_id)

    if not matched_document_ids:
        return None

    return matched_document_ids
