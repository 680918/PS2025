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

    lexical_score = overlap / len(query_tokens)

    return max(
        lexical_score,
        semantic_score,
    )


def rank_memories(
    memories,
    query=None,
    top_k=None,
):
    ranked = sorted(
        memories,
        key=lambda memory: score_memory(
            memory,
            query=query,
        ),
        reverse=True,
    )

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
