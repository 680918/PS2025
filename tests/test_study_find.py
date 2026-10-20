import secrets
import sqlite3

import pytest

from coach.learning_topics import topic_edit_version
from conversation.coach_repository import CoachRepository


def learning(
    repo,
    title,
    *,
    user="one",
    progress="讨论了提问。",
    next_step="用一个例子应用。",
    now=100,
):
    repo.create_topic(user, title, now=now)
    row = repo.active_topic(user)
    assert repo.edit_topic(
        user,
        row["topic_id"],
        title,
        progress,
        next_step,
        expected_version=topic_edit_version(row),
        now=now,
    ) in {"updated", "unchanged"}
    return row["topic_id"]


@pytest.fixture
def repo(tmp_path):
    return CoachRepository(tmp_path / "coach.db")


@pytest.mark.parametrize("field", ["title", "progress", "next_step"])
def test_find_uses_each_current_field_and_keeps_account_scope(repo, field):
    values = dict(title="阅读方法", progress="先提出问题", next_step="结合例子练习")
    values[field] += " 持久知识点"
    own = learning(repo, **values)
    learning(repo, "另一个人的学习", user="other", progress="持久知识点")
    learning(repo, "无关主题", now=110)
    before = repo.database_path.read_bytes()
    found = repo.list_topics("one", query="持久知识点")
    assert [item["topic_id"] for item in found] == [own]
    assert isinstance(found[0], dict)
    assert repo.database_path.read_bytes() == before
    assert repo.active_topic("one")["title"] == "无关主题"


@pytest.mark.parametrize(
    "query", ["python api", "ＰＹＴＨＯＮ　ＡＰＩ", "PyThOn\t \napi"]
)
def test_search_normalizes_unicode_case_and_whitespace_in_summary(repo, query):
    identity = learning(
        repo, "编程实践", progress="已讨论 Ｐｙｔｈｏｎ\n\tＡＰＩ 的用法"
    )
    assert [x["topic_id"] for x in repo.list_topics("one", query=query)] == [identity]


@pytest.mark.parametrize("query", ["100%", "a_b", "' OR 1=1 --"])
def test_search_treats_wildcards_and_sql_as_literal_text(repo, query):
    identity = learning(repo, "原样文字", next_step="练习 " + query)
    learning(repo, "不应匹配", next_step="练习 100分 aXb ordinary", now=110)
    assert [x["topic_id"] for x in repo.list_topics("one", query=query)] == [identity]


def test_fields_do_not_join_into_a_false_phrase_and_empty_query_browses_all(repo):
    first = learning(repo, "知识 甲", progress="乙 丙", next_step="丁")
    second = learning(repo, "其他主题", now=101)
    assert repo.list_topics("one", query="甲 乙") == []
    assert {x["topic_id"] for x in repo.list_topics("one", query=" \n\t")} == {
        first,
        second,
    }


def test_stable_order_pagination_and_no_duplicates_when_multiple_fields_match(repo):
    identities = [
        learning(
            repo,
            f"复习主题 {n}",
            progress="复习内容",
            next_step="复习例子",
            now=100 + n // 3,
        )
        for n in range(23)
    ]
    learning(repo, "其他主题", progress="无关内容", next_step="其他例子", now=200)
    expected = sorted(
        identities,
        key=lambda identity: (-repo.topic("one", identity)["updated_at"], identity),
    )
    first = repo.list_topics("one", query="复习", limit=11)
    second = repo.list_topics("one", query="复习", offset=10, limit=11)
    third = repo.list_topics("one", query="复习", offset=20, limit=11)
    assert [x["topic_id"] for x in first[:10] + second[:10] + third] == expected


def test_only_current_summary_is_searched_after_edit_and_restart(repo):
    identity = learning(repo, "阅读方法", progress="旧版独有概念")
    row = repo.topic("one", identity)
    assert (
        repo.edit_topic(
            "one",
            identity,
            row["title"],
            "新版独有概念",
            row["next_step"],
            expected_version=topic_edit_version(row),
            now=110,
        )
        == "updated"
    )
    restarted = CoachRepository(repo.database_path)
    assert restarted.list_topics("one", query="旧版独有概念") == []
    assert restarted.list_topics("one", query="新版独有概念")[0]["topic_id"] == identity


def test_browsing_does_not_expire_pending_request_or_change_learning(repo):
    learning(repo, "旧主题", progress="已有知识点")
    active = learning(repo, "当前主题", now=200)
    nonce = secrets.token_urlsafe(32)
    assert (
        repo.claim("one", nonce, "仍在等待的消息", now=201, ai_kind="dialogue")
        == "claimed"
    )
    before = repo.database_path.read_bytes()
    assert repo.list_topics("one", query="已有知识点")
    assert repo.active_topic("one")["topic_id"] == active
    with sqlite3.connect(repo.database_path) as db:
        assert db.execute(
            "SELECT status FROM coach_turns WHERE nonce=?", (nonce,)
        ).fetchone() == ("pending",)
        assert db.execute("SELECT count(*) FROM coach_ai_usage").fetchone() == (1,)
    assert repo.database_path.read_bytes() == before
