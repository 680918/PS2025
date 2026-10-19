import sqlite3
from uuid import uuid4

import pytest

from conversation.coach_repository import CoachRepository


def insert(
    repo,
    *,
    user="one",
    topic="表达学习",
    title="教案",
    content="共同关键词",
    status="saved",
    stamp=1000,
    favorite=False,
):
    identity = uuid4().hex
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "INSERT INTO coach_knowledge VALUES(?,?,?,?,?,?,'[]',?,?,?)",
            (
                identity,
                user,
                int(identity[:10], 16),
                title,
                topic,
                content,
                status,
                stamp,
                stamp if status == "saved" else None,
            ),
        )
        if favorite:
            db.execute(
                "INSERT INTO coach_lesson_favorites VALUES(?,?,1,1)", (user, identity)
            )
    return identity


def test_exact_topic_filter_composes_with_query_status_and_favorites_without_writes(
    tmp_path,
):
    repo = CoachRepository(tmp_path / "coach.db")
    first = insert(repo, favorite=True)
    insert(repo, topic="表达学习进阶", favorite=True)
    insert(repo, user="two", topic="他人私密主题")
    draft = insert(repo, status="pending")
    removed = insert(repo, status="dismissed")
    before = repo.database_path.read_bytes()
    assert [
        r["knowledge_id"]
        for r in repo.list_knowledge("one", topic="表达学习", query="关键词")
    ] == [first]
    assert [
        r["knowledge_id"]
        for r in repo.list_knowledge("one", topic="表达学习", favorites_only=True)
    ] == [first]
    assert repo.list_knowledge("one", topic="他人私密主题") == []
    assert repo.list_knowledge("one", topic="表达学习", query="不存在") == []
    assert (
        repo.list_knowledge("one", topic="表达学习", status="pending")[0][
            "knowledge_id"
        ]
        == draft
    )
    assert (
        repo.list_knowledge("one", topic="表达学习", status="dismissed")[0][
            "knowledge_id"
        ]
        == removed
    )
    assert (
        repo.list_knowledge(
            "one", topic="表达学习", status="pending", favorites_only=True
        )
        == []
    )
    catalog = repo.knowledge_topics("one", topic="表达学习")
    assert catalog == {
        "topics": [
            {"topic": "表达学习", "count": 1},
            {"topic": "表达学习进阶", "count": 1},
        ],
        "total": 2,
        "selected_count": 1,
        "truncated": False,
    }
    assert repo.knowledge_topics("one", favorites_only=True)["total"] == 2
    assert repo.knowledge_topics("one", status="pending")["total"] == 1
    assert repo.knowledge_topics("one", status="dismissed")["total"] == 1
    assert repo.database_path.read_bytes() == before


def test_pagination_is_after_both_topic_and_body_filter_and_keeps_existing_order(
    tmp_path,
):
    repo = CoachRepository(tmp_path / "coach.db")
    ids = [insert(repo, stamp=2000 + i) for i in range(23)]
    for i in range(25):
        insert(repo, topic="其他主题", stamp=4000 + i)
    insert(repo, content="没有目标词", stamp=5000)
    rows = repo.list_knowledge("one", topic="表达学习", query="共同", limit=20)
    tail = repo.list_knowledge(
        "one", topic="表达学习", query="共同", offset=20, limit=20
    )
    assert [r["knowledge_id"] for r in rows + tail] == list(reversed(ids))
    assert all("content" not in r for r in rows + tail)
    assert repo.knowledge_topics("one", topic="表达学习")["selected_count"] == 24
    assert repo.knowledge_topics("one")["total"] == 49


@pytest.mark.parametrize(
    "topic",
    ["%_", "' OR 1=1 --", "<script>教学</script>", 'A&B "主题"', "大小写Ａ", "a", "A"],
)
def test_topic_is_literal_exact_and_not_sql_or_normalized_guess(tmp_path, topic):
    repo = CoachRepository(tmp_path / "coach.db")
    identity = insert(repo, topic=topic)
    insert(repo, topic=topic + "扩展")
    assert [r["knowledge_id"] for r in repo.list_knowledge("one", topic=topic)] == [
        identity
    ]
    assert repo.knowledge_topics("one", topic=topic)["selected_count"] == 1


def test_bounded_options_keep_owned_counts_and_selected_old_topic_reachable(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    for i in range(205):
        insert(repo, topic=f"主题{i:03}", stamp=1000 + i)
    insert(repo, user="two", topic="他人主题", stamp=9000)
    result = repo.knowledge_topics("one", topic="主题000")
    assert (
        result["total"] == 205 and result["selected_count"] == 1 and result["truncated"]
    )
    assert len(result["topics"]) == 201 and result["topics"][0]["topic"] == "主题204"
    assert result["topics"][-1] == {"topic": "主题000", "count": 1}
    assert repo.list_knowledge("one", topic="主题000")[0]["topic"] == "主题000"
    assert len(repo.knowledge_topics("one")["topics"]) == 200
    assert repo.knowledge_topics("one", topic="不存在")["selected_count"] == 0


def test_revising_lesson_does_not_reclassify_the_original_topic(tmp_path):
    repo = CoachRepository(tmp_path / "coach.db")
    identity = insert(repo)
    assert (
        repo.revise_knowledge(
            "one", identity, 1, title="新标题", content="修订专属文字"
        )
        == "updated"
    )
    assert (
        repo.list_knowledge("one", topic="表达学习", query="修订专属文字")[0][
            "knowledge_id"
        ]
        == identity
    )
    assert repo.knowledge_topics("one")["topics"] == [{"topic": "表达学习", "count": 1}]


@pytest.mark.parametrize(
    "topic", [None, 123, "字" * 121, "换\n行", "a\x00b", "a\ud800b"]
)
def test_invalid_topic_is_rejected_before_query_and_database_is_unchanged(
    tmp_path, topic
):
    repo = CoachRepository(tmp_path / "coach.db")
    before = repo.database_path.read_bytes()
    with pytest.raises(ValueError):
        repo.list_knowledge("one", topic=topic)
    with pytest.raises(ValueError):
        repo.knowledge_topics("one", topic=topic)
    assert repo.database_path.read_bytes() == before
