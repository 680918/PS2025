"""Small user-owned reading collections referencing saved lessons, without AI."""

import json
import re
import unicodedata

from coach.unit_lessons import unit_scope_text
from coach.knowledge_search import search_query, lesson_match


MAX_BOOKLETS = 50
MAX_CHAPTERS = 100


def booklet_title(value):
    if (
        not isinstance(value, str)
        or not 1 <= len(value.strip()) <= 120
        or any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)
    ):
        raise ValueError("手册名称需要 1–120 个字符，不含换行或控制字符。")
    return value.strip()


def booklet_ids(raw):
    values = json.loads(raw)
    if (
        not isinstance(values, list)
        or len(values) > MAX_CHAPTERS
        or any(
            not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{32}", value) is None
            for value in values
        )
        or len(values) != len(set(values))
    ):
        raise ValueError("手册目录无法读取，请回到目录核对。")
    return values


def booklet_snapshot(database, user_id, identity, *, chapter=None):
    row = database.execute(
        "SELECT * FROM coach_booklets WHERE user_id=? AND booklet_id=?",
        (user_id, identity),
    ).fetchone()
    if row is None:
        return None
    book = dict(row)
    ids = booklet_ids(book.pop("lesson_ids_json"))
    book["reading_position"] = booklet_position(database, user_id, identity, ids)
    if chapter == "resume":
        chapter = book["reading_position"]["number"] or 1
    elif isinstance(chapter, str) and re.fullmatch(r"[a-f0-9]{32}", chapter):
        if chapter not in ids:
            raise LookupError("这份教案已不在本手册目录中。")
        chapter = ids.index(chapter) + 1
    book["selected_chapter"] = chapter
    has_scope = (
        database.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coach_knowledge_units'"
        ).fetchone()
        is not None
    )
    chapters = []
    for number, lesson_id in enumerate(ids, 1):
        content = chapter is None or chapter == number
        record = database.execute(
            "SELECT k.knowledge_id,k.title,k.topic,k.citations_json,COALESCE((SELECT MAX(revision) FROM coach_knowledge_versions WHERE user_id=k.user_id AND knowledge_id=k.knowledge_id),1) AS revision,"
            + ("k.content" if content else "NULL AS content")
            + " FROM coach_knowledge k WHERE k.user_id=? AND k.knowledge_id=? AND k.status='saved'",
            (user_id, lesson_id),
        ).fetchone()
        item = (
            dict(record)
            if record
            else {"knowledge_id": lesson_id, "title": "教案暂不可用", "missing": True}
        )
        item["number"] = number
        if record:
            item["citations"] = json.loads(item.pop("citations_json"))
            scope = (
                database.execute(
                    "SELECT scope_json FROM coach_knowledge_units WHERE user_id=? AND knowledge_id=?",
                    (user_id, lesson_id),
                ).fetchone()
                if has_scope
                else None
            )
            if scope:
                item["unit_summary"] = json.loads(scope[0])
        chapters.append(item)
    book["chapters"] = chapters
    return book


def booklet_search(database, user_id, identity, query, *, page=1):
    """Current saved chapters only; the caller holds one read transaction."""
    query = search_query(query)
    if not isinstance(identity, str) or re.fullmatch(r"[a-f0-9]{32}", identity) is None:
        raise ValueError("手册编号无法读取。")
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError("请检查查找结果页码。")
    row = database.execute(
        "SELECT booklet_id,title,revision,lesson_ids_json FROM coach_booklets WHERE user_id=? AND booklet_id=?",
        (user_id, identity),
    ).fetchone()
    if row is None:
        return None
    book = dict(row)
    ids = booklet_ids(book.pop("lesson_ids_json"))
    results = []
    if query:
        for number, lesson_id in enumerate(ids, 1):
            lesson = database.execute(
                "SELECT knowledge_id,title,topic,content,COALESCE((SELECT MAX(revision) FROM coach_knowledge_versions v WHERE v.user_id=k.user_id AND v.knowledge_id=k.knowledge_id),1) AS revision FROM coach_knowledge k WHERE user_id=? AND knowledge_id=? AND status='saved'",
                (user_id, lesson_id),
            ).fetchone()
            if lesson is None:
                continue
            match = lesson_match(
                lesson["title"], lesson["topic"], lesson["content"], query
            )
            if match["fields"]:
                results.append(
                    {
                        key: lesson[key]
                        for key in ("knowledge_id", "title", "topic", "revision")
                    }
                    | {"number": number, "search_match": match}
                )
    return book | {
        "query": query,
        "page": page,
        "chapter_count": len(ids),
        "total": len(results),
        "items": results[(page - 1) * 20 : page * 20],
    }


def booklet_position(database, user_id, identity, ids):
    """Resolve a user-selected chapter by ID; never infer completion or mastery."""
    empty = {"knowledge_id": None, "revision": 0, "number": None}
    if not database.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coach_booklet_positions'"
    ).fetchone():
        return empty
    row = database.execute(
        "SELECT knowledge_id,revision FROM coach_booklet_positions WHERE user_id=? AND booklet_id=?",
        (user_id, identity),
    ).fetchone()
    if row is None:
        return empty
    value = dict(row)
    readable = (
        value["knowledge_id"] in ids
        and database.execute(
            "SELECT 1 FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
            (user_id, value["knowledge_id"]),
        ).fetchone()
    )
    value["number"] = ids.index(value["knowledge_id"]) + 1 if readable else None
    return value


def booklet_position_text(book):
    position = book.get("reading_position", {})
    number = position.get("number")
    if number:
        return (
            "已记到第 " + str(number) + " 章 · " + book["chapters"][number - 1]["title"]
        )
    if position.get("knowledge_id"):
        return "之前记住的章节已移出或暂不可用，请重新选择续读位置。"
    return "尚未记住续读位置。"


def booklet_markdown(book):
    def label(text):
        return re.sub(r"([\\`*_\[\]#<>])", r"\\\1", text)

    parts = [
        "# " + label(book["title"]),
        "这是导出时的阅读副本。各章使用当时的教案版本，原教案继续保留在知识资产中。",
        label(booklet_position_text(book)) + "（阅读位置不代表学习完成或掌握程度。）",
        "## 目录",
    ]
    parts.extend(
        str(item["number"]) + ". " + label(item["title"]) for item in book["chapters"]
    )
    if not book["chapters"]:
        parts.append("尚未收录教案。")
    for item in book["chapters"]:
        parts.append("## 第 " + str(item["number"]) + " 章 · " + label(item["title"]))
        if item.get("missing"):
            parts.append("原教案暂不可用，请回到手册目录核对。")
            continue
        parts.append("教案版本：第 " + str(item["revision"]) + " 版")
        if item.get("unit_summary"):
            parts.append(unit_scope_text(item["unit_summary"]))
        parts.append(item["content"])
        if item["citations"]:
            parts.append("### 整理时参考")
            for source in item["citations"]:
                parts.append(
                    source["title"]
                    + " · "
                    + source["locator"]
                    + "\n\n"
                    + source["excerpt"]
                )
    return "\n\n".join(parts) + "\n"
