"""Bounded literal lookup of current lesson text; no AI or external index."""

import unicodedata

_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
MAX_QUERY = 120


def search_query(value):
    if not isinstance(value, str):
        raise ValueError("查找内容无法读取。")
    value = value.strip()
    if len(value) > MAX_QUERY or any(
        unicodedata.category(char) in {"Cc", "Cs"} for char in value
    ):
        raise ValueError("请使用 120 字以内的关键词或一句话，不含换行或控制字符。")
    return value


def literal_ranges(text, query):
    """Match SQLite's ASCII lower() without changing Unicode character offsets."""
    if not query:
        return
    haystack, needle = text.translate(_ASCII_LOWER), query.translate(_ASCII_LOWER)
    cursor = 0
    while (start := haystack.find(needle, cursor)) >= 0:
        yield start, start + len(query)
        cursor = start + len(query)


def match_contexts(content, query, *, limit=5):
    count = 0
    contexts = []
    last_end = 0
    for start, end in literal_ranges(content, query):
        count += 1
        if len(contexts) < limit and end > last_end:
            left, right = max(0, start - 70), min(len(content), end + 70)
            paragraph_start = content.rfind("\n", 0, start)
            paragraph_end = content.find("\n", end)
            if paragraph_start >= 0:
                left = max(left, paragraph_start + 1)
            if paragraph_end >= 0:
                right = min(right, paragraph_end)
            last_end = right
            contexts.append(
                {
                    "text": content[left:right],
                    "before": left > 0,
                    "after": right < len(content),
                }
            )
    return {"count": count, "contexts": contexts}


def lesson_match(title, topic, content, query):
    fields = [
        label
        for label, text in (("标题", title), ("主题", topic), ("正文", content))
        if next(literal_ranges(text, query), None) is not None
    ]
    matches = match_contexts(content, query, limit=1)
    excerpt = matches["contexts"][0] if matches["contexts"] else None
    return {"fields": fields, "excerpt": excerpt}
