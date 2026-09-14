import re


_INTERNAL_KNOWLEDGE_FIELDS = (
    "document_id",
    "chunk_id",
    "chunk_index",
    "score",
    "rank",
)


def apply_response_policy(content):
    if not isinstance(content, str):
        return content

    safe_content = content

    for field in _INTERNAL_KNOWLEDGE_FIELDS:
        pattern = rf"(?mi)^\s*[\"']?{re.escape(field)}[\"']?\s*[:=].*$"

        safe_content = re.sub(
            pattern,
            "",
            safe_content,
        )

    lines = [
        line
        for line in safe_content.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)