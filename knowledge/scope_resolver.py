def resolve_document_scope_with_trace(
    user_message,
    available_documents,
    top_n=None,
    min_score=1,
    min_relative_score=None,
):
    if not user_message:
        return {
            "selected_document_ids": None,
            "candidates": [],
        }

    if not available_documents:
        return {
            "selected_document_ids": None,
            "candidates": [],
        }

    normalized_message = user_message.lower()
    words = normalized_message.split()

    candidates = []

    for document in available_documents:
        # 兼容旧测试：dict + tags
        if isinstance(document, dict):
            document_id = document["id"]
            tags = document.get("tags", [])

            matched_tags = [tag for tag in tags if tag.lower() in normalized_message]

            score = len(matched_tags)

            candidates.append(
                {
                    "document_id": document_id,
                    "score": score,
                    "selected": False,
                    "matched_title_terms": [],
                    "matched_source_terms": [],
                    "matched_tags": matched_tags,
                    "reason": None,
                }
            )

            continue

        # 真实系统：KnowledgeDocument
        document_id = document.id
        title = document.title.lower()
        source = document.source.lower()

        matched_title_terms = [word for word in words if word in title]

        matched_source_terms = [word for word in words if word in source]

        score = len(matched_title_terms) * 2 + len(matched_source_terms)

        candidates.append(
            {
                "document_id": document_id,
                "score": score,
                "selected": False,
                "matched_title_terms": matched_title_terms,
                "matched_source_terms": matched_source_terms,
                "reason": None,
            }
        )

    # 先按 score 从高到低排序
    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    eligible_candidates = []

    for candidate in candidates:
        if candidate["score"] < min_score:
            candidate["reason"] = "below_min_score"
        else:
            eligible_candidates.append(candidate)

    if eligible_candidates and min_relative_score is not None:
        best_score = eligible_candidates[0]["score"]
        relative_threshold = best_score * min_relative_score

        filtered_candidates = []

        for candidate in eligible_candidates:
            if candidate["score"] < relative_threshold:
                candidate["reason"] = "below_relative_score"
            else:
                filtered_candidates.append(candidate)

        eligible_candidates = filtered_candidates

    if top_n is None:
        selected_candidates = eligible_candidates
    else:
        selected_candidates = eligible_candidates[:top_n]

    selected_ids = {candidate["document_id"] for candidate in selected_candidates}

    for candidate in candidates:
        if candidate["document_id"] in selected_ids:
            candidate["selected"] = True
            candidate["reason"] = "selected"
        elif candidate["reason"] is None:
            candidate["reason"] = "excluded_by_top_n"

    selected_document_ids = [
        candidate["document_id"] for candidate in selected_candidates
    ]

    if not selected_document_ids:
        selected_document_ids = None

    return {
        "selected_document_ids": selected_document_ids,
        "candidates": candidates,
    }


def resolve_document_scope(
    user_message,
    available_documents,
    top_n=None,
    min_score=1,
    min_relative_score=None,
):
    result = resolve_document_scope_with_trace(
        user_message,
        available_documents,
        top_n=top_n,
        min_score=min_score,
        min_relative_score=min_relative_score,
    )

    return result["selected_document_ids"]
