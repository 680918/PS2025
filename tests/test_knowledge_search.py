import sqlite3
from uuid import uuid4

import pytest

from coach.knowledge_search import search_query, literal_ranges, match_contexts
from tests import test_lesson_revision as base

setup = base.setup
saved_lesson = base.saved_lesson


def test_body_lookup_is_owned_and_separates_saved_draft_and_dismissed_without_writes(
    setup,
):
    repo, _ = setup
    saved = saved_lesson(
        repo, title="日常表达", content="先说观点，然后给一个具体例子。"
    )
    saved_lesson(
        repo, user="two", title="其他人的私人教案", content="具体例子属于其他账户。"
    )
    dismissed = saved_lesson(
        repo, title="已放弃", content="具体例子被放弃。", save=False
    )
    repo.confirm_knowledge("one", dismissed, save=False)
    draft = saved_lesson(repo, title="待确认", content="具体例子还待核对。", save=False)
    before = repo.database_path.read_bytes()
    found = repo.list_knowledge("one", query="具体例子")
    assert [item["knowledge_id"] for item in found] == [saved]
    assert found[0]["search_match"]["fields"] == ["正文"]
    assert (
        repo.list_knowledge("one", query="具体例子", status="pending")[0][
            "knowledge_id"
        ]
        == draft
    )
    assert (
        repo.list_knowledge("one", query="原始依据") == []
    )  # Citations are separate from lesson text.
    assert repo.database_path.read_bytes() == before


def test_current_revision_is_searched_and_restore_changes_results(setup):
    repo, identity = setup
    assert repo.list_knowledge("one", query="最初的例子")
    assert (
        repo.revise_knowledge(
            "one", identity, 1, title="新标题", content="新的专属概念。"
        )
        == "updated"
    )
    assert repo.list_knowledge("one", query="最初的例子") == []
    assert (
        repo.list_knowledge("one", query="新的专属概念")[0]["knowledge_id"] == identity
    )
    assert (
        repo.revise_knowledge(
            "one",
            identity,
            2,
            restore=1,
        )
        == "updated"
    )
    assert repo.list_knowledge("one", query="新的专属概念") == []
    assert repo.list_knowledge("one", query="最初的例子")
    assert repo.knowledge_version("one", identity, 2)["content"] == "新的专属概念。"


def test_bounded_excerpt_does_not_return_full_bodies_and_blank_query_keeps_metadata(
    setup,
):
    repo, _ = setup
    identity = saved_lesson(
        repo, title="长教案", content="前" * 4000 + "🧠Unique概念" + "后" * 4000
    )
    result = repo.list_knowledge("one", query="unique概念")[0]
    assert result["knowledge_id"] == identity and "content" not in result
    excerpt = result["search_match"]["excerpt"]
    assert len(excerpt["text"]) <= 260 and excerpt["before"] and excerpt["after"]
    assert "Unique概念" in excerpt["text"]
    plain = repo.list_knowledge("one", query="  ")
    assert all("content" not in item and "search_match" not in item for item in plain)


def test_query_pagination_is_applied_after_scope_and_body_filter(setup):
    repo, _ = setup
    ids = [uuid4().hex for _ in range(24)]
    with sqlite3.connect(repo.database_path) as db:
        db.executemany(
            "INSERT INTO coach_knowledge VALUES(?,'one',?,'有序教案','主题',?,'[]','saved',?,1000)",
            [
                (value, 10000 + i, "正文共同词" if i < 23 else "不命中", 2000 + i)
                for i, value in enumerate(ids)
            ],
        )
    first = repo.list_knowledge("one", query="共同词", limit=20)
    second = repo.list_knowledge("one", query="共同词", offset=20, limit=20)
    assert [item["knowledge_id"] for item in first + second] == list(reversed(ids[:23]))
    assert repo.list_knowledge("one", query="共同词", offset=100) == []


@pytest.mark.parametrize(
    "query", ["%_", "' OR 1=1 --", "A&B", "<script>", "c++", "〔知识〕"]
)
def test_punctuation_is_literal_and_ascii_case_is_ignored(setup, query):
    repo, _ = setup
    identity = saved_lesson(
        repo, title="字面查找", content="原文：" + query + " 和 HTTP api。"
    )
    found = repo.list_knowledge("one", query=query)
    assert [item["knowledge_id"] for item in found] == [identity]
    assert repo.list_knowledge("one", query="http API")[0]["knowledge_id"] == identity
    assert repo.list_knowledge("one", query="不存在%_") == []


def test_context_limit_count_and_unicode_offsets_are_consistent_with_database():
    text = "😀前言İ " + (("Knowledge知识；" + "间隔" * 100) * 8)
    assert list(literal_ranges("İ AİB", "aİb")) == [(2, 5)]
    assert list(literal_ranges("İ", "i")) == []
    result = match_contexts(text, "knowledge知识")
    assert result["count"] == 8 and len(result["contexts"]) == 5
    assert all("Knowledge知识" in excerpt["text"] for excerpt in result["contexts"])
    assert match_contexts(text, "") == {"count": 0, "contexts": []}


def test_body_context_stays_in_relevant_paragraph_instead_of_copying_adjacent_headings():
    content = "## 学习目标\n先说出一个观点。\n\n## 核心知识\n再给一个具体例子，核对理解。\n\n## 其他章节\n完全不同的事情。"
    result = match_contexts(content, "具体例子")
    assert result["count"] == 1
    assert result["contexts"][0]["text"] == "再给一个具体例子，核对理解。"


@pytest.mark.parametrize("query", ["字" * 121, "a\nb", "a\x00b", "a\ud800b", None, 12])
def test_invalid_queries_are_rejected_before_database_work(setup, query):
    repo, _ = setup
    before = repo.database_path.read_bytes()
    with pytest.raises(ValueError):
        repo.list_knowledge("one", query=query)
    assert repo.database_path.read_bytes() == before
    with pytest.raises(ValueError):
        search_query(query)
