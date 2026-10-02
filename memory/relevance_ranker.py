import re

_SEMANTIC_ALIAS_GROUPS = (
    (
        "agent",
        "智能体",
    ),
    (
        "tool calling",
        "工具调用",
        "调用外部工具",
    ),
)


def _normalize_text(text):
    return str(text or "").lower().strip()


def _tokenize(text):
    return set(
        re.findall(
            r"\w+",
            _normalize_text(text),
        )
    )


def score_memory(
    memory,
    query=None,
):
    normalized_query = _normalize_text(query)

    if not normalized_query:
        return 0.0

    normalized_content = _normalize_text(memory.get("content", ""))

    if normalized_query in normalized_content:
        return 1.0

    semantic_score = _semantic_alias_score(
        normalized_query,
        normalized_content,
    )

    query_tokens = _tokenize(normalized_query)

    content_tokens = _tokenize(normalized_content)

    if not query_tokens:
        return semantic_score

    overlap = len(query_tokens & content_tokens)

    if overlap == len(query_tokens):
        lexical_score = 1.0

    elif overlap > 0:
        lexical_score = (overlap / len(query_tokens)) * 0.5

    else:
        lexical_score = 0.0

    return max(
        lexical_score,
        semantic_score,
    )


def rank_memories(
    memories,
    query=None,
    top_k=None,
    threshold=None,
    score_gap_threshold=None,
):
    scored_memories = []

    for memory in memories:
        score = score_memory(
            memory,
            query,
        )

        scored_memories.append(
            (
                memory,
                score,
            )
        )

    sorted_memories = sorted(
        scored_memories,
        key=lambda item: item[1],
        reverse=True,
    )

    if threshold is not None:
        filtered = [memory for memory, score in sorted_memories if score > threshold]

        if filtered:
            ranked = filtered
        else:
            ranked = [sorted_memories[0][0]]

    else:
        ranked = [memory for memory, _ in sorted_memories]

        if score_gap_threshold is not None and len(ranked) >= 2:
            top_score = score_memory(
                ranked[0],
                query,
            )

            second_score = score_memory(
                ranked[1],
                query,
            )

            if top_score - second_score >= score_gap_threshold:
                ranked = [ranked[0]]

    if top_k is None:
        return ranked

    return ranked[:top_k]


def _matched_semantic_groups(text):
    normalized_text = _normalize_text(text)

    matched_groups = set()

    for index, aliases in enumerate(_SEMANTIC_ALIAS_GROUPS):
        if any(alias in normalized_text for alias in aliases):
            matched_groups.add(index)

    return matched_groups


def _semantic_alias_score(
    query,
    content,
):
    query_groups = _matched_semantic_groups(query)

    if not query_groups:
        return 0.0

    content_groups = _matched_semantic_groups(content)

    matched_groups = query_groups & content_groups

    return len(matched_groups) / len(query_groups)
