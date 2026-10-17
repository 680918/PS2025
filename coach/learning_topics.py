"""Small helpers for user-owned topics and the material actually used in discussion."""

import unicodedata


class TopicBusy(ValueError):
    pass


def topic_key(title):
    return " ".join(unicodedata.normalize("NFKC", title).casefold().split())


def validate_topic_title(title):
    if (
        not isinstance(title, str)
        or not 1 <= len(title.strip()) <= 120
        or any(unicodedata.category(char) in {"Cc", "Cs"} for char in title)
    ):
        raise ValueError("学习主题需要 1–120 个字符，不含换行或控制字符。")
    return title.strip()


def discussion_material(dialogue, materials, user_id):
    if materials is None:
        return None
    topic = dialogue.active_topic(user_id)
    # NULL means an old internal caller did not supply material context. Empty
    # string is an explicit topic with no material and must never fall back.
    if topic is not None and topic["material_id"] is not None:
        return (
            materials.get(user_id, topic["material_id"])
            if topic["material_id"]
            else None
        )
    return materials.selected(user_id)


def select_discussion_material(dialogue, materials, user_id, material_id=None):
    if material_id is not None and materials.get(user_id, material_id) is None:
        raise ValueError("找不到这份资料。")
    dialogue.bind_topic_material(
        user_id,
        material_id or "",
        default_selector=lambda: materials.select(user_id, material_id),
    )
