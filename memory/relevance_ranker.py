import re


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

    query_tokens = _tokenize(normalized_query)
    content_tokens = _tokenize(normalized_content)

    if not query_tokens:
        return 0.0

    overlap = len(query_tokens & content_tokens)

    return overlap / len(query_tokens)


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
