def resolve_document_scope(
    user_message,
    available_documents,
    top_n=None,
):
    if not user_message:
        return None

    if not available_documents:
        return None

    normalized_message = user_message.lower()

    scored_documents = []

    for document in available_documents:
        # 兼容旧测试：dict + tags
        if isinstance(document, dict):
            document_id = document["id"]
            tags = document.get("tags", [])

            score = 0

            for tag in tags:
                if tag.lower() in normalized_message:
                    score += 1

            if score > 0:
                scored_documents.append(
                    (
                        score,
                        document_id,
                    )
                )

            continue

        # 真实系统：KnowledgeDocument
        document_id = document.id
        title = document.title.lower()
        source = document.source.lower()

        words = normalized_message.split()

        score = 0

        for word in words:
            if word in title:
                score += 2

            if word in source:
                score += 1

        if score > 0:
            scored_documents.append(
                (
                    score,
                    document_id,
                )
            )

    if not scored_documents:
        return None

    scored_documents.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    document_ids = [document_id for score, document_id in scored_documents]

    if top_n is not None:
        document_ids = document_ids[:top_n]

    return document_ids
