import smtplib
import sqlite3
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from tests import test_web_studies as base
from tests.test_web_coach_dialogue import BASE, Forms, login
from tests.test_web_knowledge_search import Links
from tests.test_conversation_review import turn, topic

setup = base.setup
password_hash = base.password_hash
no_paid_services = base.no_paid_services


@pytest.fixture(autouse=True)
def no_plain_smtp(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: pytest.fail("No real SMTP"))


def records(text):
    return [
        link for link in Links(text).links if link.startswith("/web/conversations/")
    ]


def assert_safe_copy_page(text):
    script = '<script src="/static/content-copy.js?v=1" defer></script>'
    assert text.count(script) == 1
    assert Links(text.replace(script, "")).active == []


def test_old_dialogue_search_read_and_explicit_topic_switch_keep_the_same_chat(setup):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    a = topic(repo, "清晰表达", user=user.user_id)
    old = turn(
        repo,
        "为什么要用具体例子？",
        "## 先说观点\n再用一个具体例子帮助对方理解。",
        user=user.user_id,
    )
    b = topic(repo, "时间管理", user=user.user_id, now=200)
    for number in range(45):
        turn(repo, "时间安排" + str(number), user=user.user_id, now=300 + number * 2)
    before = {
        path: path.read_bytes()
        for path in (repo.database_path, materials.database_path)
    }
    found = client.get("/web/conversations", params={"q": "具体例子"})
    assert found.status_code == 200 and len(records(found.text)) == 1
    assert "<mark>具体例子</mark>" in found.text
    detail = client.get(records(found.text)[0])
    assert detail.status_code == 200 and "<h2>先说观点</h2>" in detail.text
    assert "为什么要用<mark>具体例子</mark>？" in detail.text
    assert "回到这个学习主题" in detail.text
    assert repo.active_topic(user.user_id)["topic_id"] == b and calls == []
    assert all(path.read_bytes() == data for path, data in before.items())
    path = f"/web/studies/{a}/open"
    values = Forms(detail.text).values(path)
    result = client.post(path, data=values)
    assert (
        result.status_code == 200 and repo.active_topic(user.user_id)["topic_id"] == a
    )
    assert calls == [] and "清晰表达" in result.text
    assert repo.conversation_record(user.user_id, old)["assistant_content"].startswith(
        "## 先说观点"
    )


def test_paging_filters_detail_and_neighbors_preserve_original_results(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    a = topic(repo, "表达主题", user=user.user_id)
    ids = [
        turn(repo, "查找词" + str(index), user=user.user_id, now=100 + index * 2)
        for index in range(25)
    ]
    topic(repo, "其他主题", user=user.user_id, now=200)
    turn(repo, "查找词，但属于其他主题", user=user.user_id, now=201)
    first = client.get("/web/conversations", params={"q": "查找词", "topic": a})
    assert len(records(first.text)) == 20
    next_page = next(
        link
        for link in Links(first.text).links
        if link.startswith("/web/conversations?") and "page=2" in link
    )
    second = client.get(next_page)
    assert len(records(second.text)) == 5 and "下一页 →" not in second.text
    detail = client.get(records(second.text)[0])
    back = next(
        link
        for link in Links(detail.text).links
        if link.startswith("/web/conversations?")
    )
    assert parse_qs(urlsplit(back).query) == {
        "q": ["查找词"],
        "topic": [a],
        "page": ["2"],
    }
    previous = next(
        link for link in records(detail.text) if "/" + str(ids[3]) + "?" in link
    )
    assert parse_qs(urlsplit(previous).query)["page"] == ["2"]
    assert calls == []


def test_archive_source_snapshots_saved_assets_and_drafts_stay_separate(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    sources = [
        {
            "source_id": "a" * 32,
            "material_id": "b" * 32,
            "title": "<原书>",
            "locator": "PDF 第 3 页",
            "excerpt": "当时引用的原文 <img src=x>。",
        }
    ]
    identity = turn(
        repo,
        "整理知识点",
        user=user.user_id,
        citations=sources,
        draft={"title": "一份教案", "topic": "表达", "content": "最初的正文。"},
    )
    draft = repo.list_knowledge(user.user_id, status="pending")[0]
    detail = client.get(f"/web/conversations/{identity}")
    assert "待你确认的草稿" in detail.text and draft["knowledge_id"] in detail.text
    assert "当时引用的原文 &lt;img src=x&gt;" in detail.text
    assert repo.knowledge(user.user_id, draft["knowledge_id"])["status"] == "pending"
    repo.confirm_knowledge(user.user_id, draft["knowledge_id"])
    repo.revise_knowledge(
        user.user_id,
        draft["knowledge_id"],
        1,
        title="后来修订的教案",
        content="新的正文。",
    )
    detail = client.get(f"/web/conversations/{identity}")
    assert "后来修订的教案" in detail.text and "已保存教案" in detail.text
    assert "当时引用的原文" in detail.text and calls == []
    assert_safe_copy_page(detail.text)


def test_unclassified_failed_pending_and_no_match_pages_do_not_retry_or_expire(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    failed = turn(repo, "早期未成功的消息", user=user.user_id, status="failed")
    pending = turn(repo, "仍未完成的消息", user=user.user_id, status="pending", now=105)
    before = repo.database_path.read_bytes()
    listed = client.get("/web/conversations?topic=unfiled")
    assert "未归入学习主题" in listed.text and "未取得回复" in listed.text
    detail = client.get(f"/web/conversations/{pending}?q=不存在的词&topic=unfiled")
    assert "本轮尚未记录完整回复" in detail.text and "没有匹配文字" in detail.text
    assert "回到这个学习主题" not in detail.text
    failed_page = client.get(f"/web/conversations/{failed}")
    assert (
        "早期未成功的消息" in failed_page.text and "这轮未取得回复" in failed_page.text
    )
    assert repo.database_path.read_bytes() == before and calls == []


def test_login_ownership_filter_and_direct_detail_cannot_expose_other_accounts(setup):
    app, client, repo, _, user, other, calls = setup
    login(client)
    private = topic(repo, "私有主题标题", user=user.user_id)
    identity = turn(repo, "只属于这个账户的暗号", user=user.user_id)
    with TestClient(app, base_url=BASE) as stranger:
        assert (
            stranger.get("/web/conversations", follow_redirects=False).status_code
            == 303
        )
        assert (
            stranger.get(
                f"/web/conversations/{identity}", follow_redirects=False
            ).status_code
            == 303
        )
        login(stranger, "two@example.com")
        found = stranger.get("/web/conversations?q=暗号")
        assert "只属于这个账户" not in found.text and "私有主题标题" not in found.text
        assert (
            stranger.get("/web/conversations", params={"topic": private}).status_code
            == 404
        )
        assert stranger.get(f"/web/conversations/{identity}").status_code == 404
    assert calls == []


def test_html_queries_messages_topics_and_markdown_remain_inert(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    topic(repo, "</title><script>alert(1)</script>", user=user.user_id)
    query = "<img src=x onerror=alert(2)>"
    turn(
        repo,
        query,
        '## 标题\n<script>alert(3)</script>\n\n```python\nif ok:\n    print("保留缩进")\n```\n\n| 项目 | 方法 |\n| --- | --- |\n| 学习 | 原文 |',
        user=user.user_id,
    )
    found = client.get("/web/conversations", params={"q": query})
    detail = client.get(records(found.text)[0])
    for response in (found, detail):
        assert response.status_code == 200
        if response is detail:
            assert_safe_copy_page(response.text)
            assert "script-src 'self'" in response.headers["content-security-policy"]
        else:
            assert Links(response.text).active == []
        assert "<mark>&lt;img src=x onerror=alert(2)&gt;</mark>" in response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
    assert "    print(&quot;保留缩进&quot;)" in detail.text and "<table>" in detail.text
    assert (
        "frame-ancestors" in detail.headers["content-security-policy"] and calls == []
    )


@pytest.mark.parametrize("kind", ["csrf", "other-topic", "cross-site", "other-session"])
def test_archive_switch_reuses_protected_explicit_topic_action(setup, kind):
    app, client, repo, _, user, _, calls = setup
    login(client)
    a = topic(repo, "旧主题", user=user.user_id)
    identity = turn(repo, "旧的讨论", user=user.user_id)
    b = topic(repo, "当前主题", user=user.user_id, now=105)
    detail = client.get(f"/web/conversations/{identity}")
    path = f"/web/studies/{a}/open"
    values = Forms(detail.text).values(path)
    headers = {}
    if kind == "csrf":
        values["csrf"] = "0" * 64
    if kind == "other-topic":
        path = f"/web/studies/{b}/open"
    if kind == "cross-site":
        headers = {"origin": "https://outside.example", "sec-fetch-site": "cross-site"}
    if kind == "other-session":
        with TestClient(app, base_url=BASE) as another:
            login(another)
            result = another.post(path, data=values)
    else:
        result = client.post(path, data=values, headers=headers)
    assert (
        result.status_code == 403
        and repo.active_topic(user.user_id)["topic_id"] == b
        and calls == []
    )


def test_current_inflight_reply_blocks_explicit_switch_but_allows_reading(setup):
    _, client, repo, _, user, _, calls = setup
    from time import time

    login(client)
    a = topic(repo, "旧主题", user=user.user_id)
    identity = turn(repo, "旧问题", user=user.user_id)
    b = topic(repo, "当前主题", user=user.user_id, now=105)
    turn(repo, "正在等回复", user=user.user_id, status="pending", now=int(time()))
    detail = client.get(f"/web/conversations/{identity}")
    assert detail.status_code == 200
    path = f"/web/studies/{a}/open"
    assert client.post(path, data=Forms(detail.text).values(path)).status_code == 409
    assert repo.active_topic(user.user_id)["topic_id"] == b and calls == []


@pytest.mark.parametrize(
    "query",
    [
        "q=" + "x" * 121,
        "q=a%0Ab",
        "q=a%00b",
        "q=a&q=b",
        "topic=../outside",
        "topic=a&topic=b",
        "page=0",
        "page=10001",
        "page=1.5",
        "page=1&page=2",
    ],
)
def test_invalid_filters_are_rejected_on_index_and_detail_without_mutation(
    setup, query
):
    _, client, repo, _, user, _, calls = setup
    login(client)
    identity = turn(repo, "有内容", user=user.user_id)
    before = repo.database_path.read_bytes()
    for path in ("/web/conversations", f"/web/conversations/{identity}"):
        assert client.get(path + "?" + query).status_code == 400
    assert repo.database_path.read_bytes() == before and calls == []


def test_unknown_records_scope_mismatch_and_internal_errors_are_safe(
    setup, monkeypatch
):
    _, client, repo, _, user, _, calls = setup
    login(client)
    topic(repo, "主题甲", user=user.user_id)
    identity = turn(repo, "问题", user=user.user_id)
    b = topic(repo, "主题乙", user=user.user_id, now=110)
    assert client.get(f"/web/conversations/{identity}?topic={b}").status_code == 404
    for value in ("0", "-1", "abc", "9223372036854775808", "999999"):
        assert client.get("/web/conversations/" + value).status_code == 404

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("private path with internal credentials")

    monkeypatch.setattr(base.CoachRepository, "conversation_records", broken)
    result = client.get("/web/conversations")
    assert (
        result.status_code == 503 and "private path" not in result.text and calls == []
    )


def test_browse_empty_archive_and_live_workspace_offer_clear_entry_points(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    assert "这里还没有对话记录" in client.get("/web/conversations").text
    assert 'href="/web/conversations"' in client.get("/web/welcome").text
    a = topic(repo, "有目录的主题", user=user.user_id)
    study = client.get("/web/studies")
    assert f'href="/web/conversations?topic={a}"' in study.text
    assert "回看主题对话" in study.text and calls == []


def test_selected_older_topic_stays_available_beyond_recent_dropdown_limit(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    old = topic(repo, "较早的学习主题", user=user.user_id, now=1)
    turn(repo, "较早的讨论", user=user.user_id, now=2)
    for index in range(101):
        topic(repo, "后来的主题" + str(index), user=user.user_id, now=100 + index)
    result = client.get("/web/conversations", params={"topic": old})
    assert result.status_code == 200 and "最近更新的 100 个主题" in result.text
    assert f'<option value="{old}" selected>较早的学习主题</option>' in result.text
    assert len(records(result.text)) == 1 and calls == []


def test_ai_disabled_still_supports_archive_browsing_and_explicit_switch(
    setup, tmp_path
):
    _, _, repo, _, user, _, calls = setup
    from api.account_app import create_account_app

    selected = topic(repo, "不启用AI也能回看的主题", user=user.user_id)
    identity = turn(repo, "已有的问答", user=user.user_id)
    with TestClient(create_account_app(tmp_path), base_url=BASE) as client:
        login(client)
        detail = client.get(f"/web/conversations/{identity}")
        assert detail.status_code == 200 and "已有的问答" in detail.text
        path = f"/web/studies/{selected}/open"
        assert (
            client.post(path, data=Forms(detail.text).values(path)).status_code == 200
        )
    assert calls == []
