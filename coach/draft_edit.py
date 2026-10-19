"""Version checks and validation for explicit changes to pending lesson drafts."""

import hashlib
import json
import unicodedata


def draft_version(item):
    return hashlib.sha256(
        json.dumps(
            [item[key] for key in ("knowledge_id", "status", "title", "content")]
            + [item["draft_generation"] if "draft_generation" in item.keys() else 0],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def draft_text(title, content):
    if isinstance(content, str):
        content = content.replace("\r\n", "\n").replace("\r", "\n")
    if (
        not isinstance(title, str)
        or not 1 <= len(title.strip()) <= 120
        or any(unicodedata.category(c) in {"Cc", "Cs"} for c in title)
    ):
        raise ValueError("标题需要 1–120 字，不含换行或控制字符。")
    if (
        not isinstance(content, str)
        or not 1 <= len(content.strip()) <= 12000
        or any(
            unicodedata.category(c) in {"Cc", "Cs"} and c not in "\n\t" for c in content
        )
    ):
        raise ValueError("正文需要 1–12000 字，不含无效控制字符。")
    return title.strip(), content.strip()
