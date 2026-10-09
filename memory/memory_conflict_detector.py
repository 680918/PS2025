def _normalize_content(
    content,
):
    if not isinstance(content, str):
        return content

    return " ".join(content.split())


def detect_memory_conflict(
    existing,
    incoming,
):
    existing_slot = (
        existing.get("memory_type"),
        existing.get("memory_key"),
    )

    incoming_slot = (
        incoming.get("memory_type"),
        incoming.get("memory_key"),
    )

    if existing_slot != incoming_slot:
        return {
            "has_conflict": False,
            "reason": "different_slot",
        }

    existing_content = _normalize_content(existing.get("content"))

    incoming_content = _normalize_content(incoming.get("content"))

    if existing_content == incoming_content:
        return {
            "has_conflict": False,
            "reason": "same_content",
        }

    return {
        "has_conflict": True,
        "reason": "same_slot_content_changed",
    }
