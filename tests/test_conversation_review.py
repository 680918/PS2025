import secrets
from contextlib import closing

import pytest

from conversation.coach_repository import CoachRepository


def turn(
    repo,
    text,
    reply="记录中的回复。",
    *,
    user="one",
    now=100,
    status="complete",
    draft=None,
    citations=None,
    detached=False,
):
    nonce = secrets.token_urlsafe(32)
    assert repo.claim(user, nonce, text, now=now, detached=detached) == "claimed"
    if status == "complete":
        assert repo.finish(
            user, nonce, reply, None, now=now + 1, draft=draft, citations=citations
        )
    elif status == "failed":
        repo.fail(user, nonce, now=now + 1)
    with closing(repo._connect()) as db:
        return db.execute(
            "SELECT turn_id FROM coach_turns WHERE user_id=? AND nonce=?", (user, nonce)
        ).fetchone()[0]


def topic(repo, title, *, user="one", now=50):
    repo.create_topic(user, title, now=now)
    return repo.active_topic(user)["topic_id"]


@pytest.fixture
def repo(tmp_path):
    return CoachRepository(tmp_path / "conversations.db")


def test_search_beyond_live_history_matches_both_speakers_and_keeps_bounded_excerpts(
    repo,
):
    first = turn(
        repo, "我的独特问题：如何应用？", "前文" * 800 + "持久知识点" + "后文" * 800
    )
    for number in range(45):
        turn(repo, f"后来的第{number}轮", now=200 + number * 2)
    assert first not in [item["turn_id"] for item in repo.view("one", now=400)["turns"]]
    before = repo.database_path.read_bytes()
    own_question = repo.conversation_records("one", query="独特问题")
    own_answer = repo.conversation_records("one", query="持久知识点")
    assert [item["turn_id"] for item in own_question] == [first]
    assert [part["speaker"] for part in own_question[0]["excerpts"]] == ["你"]
    assert [item["turn_id"] for item in own_answer] == [first]
    assert [part["speaker"] for part in own_answer[0]["excerpts"]] == ["知行"]
    assert len(own_answer[0]["excerpts"][0]["text"]) <= 145
    assert all(
        key not in own_answer[0]
        for key in (
            "nonce",
            "user_id",
            "assistant_content",
            "user_content",
            "citations_json",
        )
    )
    assert repo.database_path.read_bytes() == before
    assert (
        CoachRepository(repo.database_path).conversation_records(
            "one", query="持久知识点"
        )
        == own_answer
    )


def test_empty_query_browses_every_owned_round_with_a_sentinel_and_stable_order(repo):
    ids = [
        turn(repo, "问题" + str(number), now=100 + number * 2) for number in range(25)
    ]
    first = repo.conversation_records("one")
    second = repo.conversation_records("one", page=2)
    assert len(first) == 21 and len(second) == 5
    assert [item["turn_id"] for item in first[:20] + second] == list(reversed(ids))
    assert repo.conversation_records("one", page=3) == []


def test_filtering_preserves_actual_early_and_detached_records_without_guessing_topics(
    repo,
):
    early = turn(repo, "时间管理的早期问题")
    a = topic(repo, "时间管理", now=110)
    a_turn = turn(repo, "正式学习第一轮", now=111)
    detached = turn(repo, "独立整理请求", now=113, detached=True)
    b = topic(repo, "阅读方法", now=120)
    b_turn = turn(repo, "正式学习第二轮", now=121)
    before = repo.database_path.read_bytes()
    assert [
        item["turn_id"] for item in repo.conversation_records("one", topic_id=a)
    ] == [a_turn]
    assert [
        item["turn_id"] for item in repo.conversation_records("one", topic_id=b)
    ] == [b_turn]
    assert [
        item["turn_id"] for item in repo.conversation_records("one", topic_id="unfiled")
    ] == [detached, early]
    assert (
        repo.active_topic("one")["topic_id"] == b
        and repo.database_path.read_bytes() == before
    )


def test_neighbors_follow_same_stored_topic_and_do_not_cross_other_users(repo):
    a = topic(repo, "主题甲")
    a1 = turn(repo, "甲1")
    b = topic(repo, "主题乙", now=105)
    turn(repo, "乙1", now=106)
    foreign = turn(repo, "不公开的对话", user="two", now=108)
    repo.activate_topic("one", a, now=110)
    a2 = turn(repo, "甲2", now=111)
    repo.activate_topic("one", b, now=115)
    turn(repo, "乙2", now=116)
    repo.activate_topic("one", a, now=120)
    a3 = turn(repo, "甲3", now=121)
    detail = repo.conversation_record("one", a2)
    assert detail["neighbors"] == {"previous": a1, "next": a3}
    assert repo.conversation_record("one", a1)["neighbors"]["previous"] is None
    assert repo.conversation_record("one", a3)["neighbors"]["next"] is None
    assert repo.conversation_record("one", foreign) is None
    assert repo.conversation_records("two", query="甲") == []


def test_saved_draft_and_citations_are_read_from_the_original_round_only(repo):
    sources = [
        {
            "source_id": "a" * 32,
            "material_id": "b" * 32,
            "title": "原来的书",
            "locator": "片段 3",
            "excerpt": "当时真实引用的原文。",
        }
    ]
    identity = turn(
        repo,
        "帮我整理教案",
        draft={"title": "原始草稿", "topic": "学习", "content": "教案正文。"},
        citations=sources,
    )
    draft = repo.list_knowledge("one", status="pending")[0]
    detail = repo.conversation_record("one", identity)
    assert detail["citations"] == sources
    assert detail["lessons"] == [
        {
            "knowledge_id": draft["knowledge_id"],
            "title": "原始草稿",
            "status": "pending",
        }
    ]
    repo.confirm_knowledge("one", draft["knowledge_id"])
    repo.revise_knowledge(
        "one", draft["knowledge_id"], 1, title="修订后的标题", content="新的内容。"
    )
    saved = repo.conversation_record("one", identity)
    assert (
        saved["lessons"][0]["status"] == "saved"
        and saved["lessons"][0]["title"] == "修订后的标题"
    )
    assert (
        saved["citations"] == sources and saved["assistant_content"] == "记录中的回复。"
    )
    assert repo.conversation_record("two", identity) is None


def test_dismissed_draft_is_not_resurrected_by_reading(repo):
    identity = turn(
        repo,
        "请求",
        draft={"title": "放弃的草稿", "topic": "学习", "content": "正文。"},
    )
    draft = repo.list_knowledge("one", status="pending")[0]
    repo.confirm_knowledge("one", draft["knowledge_id"], save=False)
    assert repo.conversation_record("one", identity)["lessons"] == []


def test_lookup_does_not_expire_pending_calls_or_change_failed_records(repo):
    failed = turn(repo, "失败的原消息", status="failed")
    pending = turn(repo, "未完成的原消息", status="pending", now=105)
    before = repo.database_path.read_bytes()
    assert repo.conversation_record("one", pending)["status"] == "pending"
    assert repo.conversation_record("one", failed)["status"] == "failed"
    assert len(repo.conversation_records("one")) == 2
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize(
    "query,expected",
    [
        ("ABC", True),
        ("abc", True),
        ("%_'", True),
        ("' OR 1=1 --", False),
        ("ss", False),
        ("i", False),
    ],
)
def test_search_uses_literal_text_and_sqlite_ascii_matching(repo, query, expected):
    turn(repo, "ABC %_' İ ß", reply="回复")
    assert bool(repo.conversation_records("one", query=query)) == expected


def test_another_users_topic_tag_cannot_leak_a_title_or_change_ownership(repo):
    identity = turn(repo, "自己的对话")
    foreign = topic(repo, "别人的私有主题", user="two", now=110)
    with closing(repo._connect()) as db, db:
        db.execute(
            "INSERT INTO coach_turn_topics VALUES(?,?,?)", (identity, "one", foreign)
        )
    detail = repo.conversation_record("one", identity)
    assert detail["topic_title"] is None and detail["topic_id"] is None
    assert repo.conversation_records("one", topic_id=foreign) == []
    assert (
        repo.conversation_records("one", topic_id="unfiled")[0]["turn_id"] == identity
    )


@pytest.mark.parametrize("query", [None, 42, "a" * 121, "a\nb", "a\0b", "a\ud800b"])
def test_invalid_query_is_rejected(repo, query):
    with pytest.raises(ValueError):
        repo.conversation_records("one", query=query)


@pytest.mark.parametrize("number", [True, 0, -1, "1", 1.5, 10001])
def test_bad_page_is_rejected(repo, number):
    with pytest.raises(ValueError):
        repo.conversation_records("one", page=number)


@pytest.mark.parametrize("identity", [True, 0, -1, "1", 1.5, 9223372036854775808])
def test_bad_record_identifier_is_rejected(repo, identity):
    with pytest.raises(ValueError):
        repo.conversation_record("one", identity)


@pytest.mark.parametrize("scope", [None, 42, "../outside", "x" * 32])
def test_bad_topic_filter_is_rejected(repo, scope):
    with pytest.raises(ValueError):
        repo.conversation_records("one", topic_id=scope)
