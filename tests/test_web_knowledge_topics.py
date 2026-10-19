import sqlite3
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from tests import test_web_lesson_revision as base
from tests.test_web_coach_dialogue import login
from tests.test_web_knowledge_search import Links, result_link
from tests.test_knowledge_topics import insert

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


class Options(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.options = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            self.options.append(dict(attrs))


def params(url):
    return parse_qs(urlsplit(url).query)


def test_filter_search_paging_detail_and_back_keep_same_scope_without_learning_writes(
    setup,
):
    _, client, repo, user, _ = setup
    topic = "表达 & 实践"
    ids = [
        insert(
            repo, user=user.user_id, topic=topic, title=f"主题内教案{i}", stamp=3000 + i
        )
        for i in range(23)
    ]
    insert(repo, user=user.user_id, topic="其他主题", title="其他主题专属教案")
    insert(repo, user="other", topic="私人主题不显示", title="别人的教案")
    before = repo.database_path.read_bytes()
    found = client.get("/web/knowledge", params={"q": "共同关键词", "topic": topic})
    assert (
        found.status_code == 200
        and "其他主题专属教案" not in found.text
        and "私人主题不显示" not in found.text
    )
    assert "本目录共 25 份" in found.text and "共 23 份" in found.text
    assert any(
        o.get("value") == topic and "selected" in o for o in Options(found.text).options
    )
    next_url = next(
        url
        for url in Links(found.text).links
        if url.startswith("?") and params(url).get("page") == ["2"]
    )
    assert params(next_url)["topic"] == [topic] and params(next_url)["q"] == [
        "共同关键词"
    ]
    second = client.get("/web/knowledge" + next_url)
    detail_link = result_link(second.text, ids[0])
    assert params(detail_link)["result_page"] == ["2"] and params(detail_link)[
        "topic"
    ] == [topic]
    detail = client.get(detail_link)
    back = next(
        url for url in Links(detail.text).links if url.startswith("/web/knowledge?")
    )
    assert params(back) == {
        "q": ["共同关键词"],
        "status": ["saved"],
        "page": ["2"],
        "topic": [topic],
    }
    assert "当前正文共 1 处匹配" in detail.text
    assert repo.database_path.read_bytes() == before
    assert client.get(back).status_code == 200


@pytest.mark.parametrize(
    "path,status,favorite",
    [
        ("/web/knowledge", "saved", False),
        ("/web/knowledge?status=pending", "pending", False),
        ("/web/knowledge-favorites", "saved", True),
        ("/web/knowledge-removed", "dismissed", False),
    ],
)
def test_each_directory_has_owned_topics_and_keeps_topic_on_tabs_clear_and_back(
    setup, path, status, favorite
):
    _, client, repo, user, _ = setup
    topic = "编程入门"
    identity = insert(
        repo, user=user.user_id, topic=topic, status=status, favorite=favorite
    )
    insert(
        repo,
        user=user.user_id,
        topic="不应显示的别种状态",
        status="pending" if status == "saved" else "saved",
    )
    if favorite:
        insert(repo, user=user.user_id, topic="未收藏不计入主题")
    page = client.get(
        path.split("?")[0], params={"topic": topic, "q": "共同", "status": status}
    )
    assert page.status_code == 200
    assert "不应显示的别种状态" not in [
        o.get("value") for o in Options(page.text).options
    ]
    if favorite:
        assert "未收藏不计入主题" not in page.text
    links = Links(page.text).links
    clear = next(
        url
        for url in links
        if url.startswith("?")
        and params(url).get("topic") == [topic]
        and "q" not in params(url)
        and "page" not in params(url)
    )
    assert params(clear).get("status") == [status]
    tabs = [
        url
        for url in links
        if url.startswith(
            ("/web/knowledge?", "/web/knowledge-favorites?", "/web/knowledge-removed?")
        )
    ]
    assert tabs and all(params(url).get("topic") == [topic] for url in tabs)
    target = next(
        url
        for url in links
        if url.startswith(
            (
                "/web/knowledge/" + identity + "?",
                "/web/knowledge-removed/" + identity + "?",
            )
        )
    )
    detail = client.get(target)
    back = next(
        url
        for url in Links(detail.text).links
        if url.startswith(
            "/web/knowledge-removed?"
            if status == "dismissed"
            else "/web/knowledge-favorites?"
            if favorite
            else "/web/knowledge?"
        )
    )
    assert params(back)["topic"] == [topic]
    assert client.get(back).status_code == 200


def test_topic_only_browsing_has_return_link_and_empty_scope_can_be_cleared(setup):
    _, client, repo, user, _ = setup
    identity = insert(repo, user=user.user_id, topic="纯浏览主题")
    found = client.get("/web/knowledge", params={"topic": "纯浏览主题"})
    detail = client.get(result_link(found.text, identity))
    assert "返回主题目录" in detail.text
    back = next(
        url for url in Links(detail.text).links if url.startswith("/web/knowledge?")
    )
    assert params(back)["topic"] == ["纯浏览主题"]
    empty = client.get(
        "/web/knowledge", params={"topic": "不存在的主题", "q": "关键词"}
    )
    assert "当前主题下没有匹配内容" in empty.text and "共 0 份" in empty.text
    assert any(
        params(url).get("q") == ["关键词"] and "topic" not in params(url)
        for url in Links(empty.text).links
        if url.startswith("?")
    )


@pytest.mark.parametrize(
    "topic", ["<script>alert(1)</script>", '" onclick="alert(1)', "A&B %_"]
)
def test_topic_names_are_escaped_in_options_summary_and_links(setup, topic):
    _, client, repo, user, _ = setup
    identity = insert(repo, user=user.user_id, topic=topic)
    found = client.get("/web/knowledge", params={"topic": topic})
    assert found.status_code == 200 and Links(found.text).active == []
    assert any(o.get("value") == topic for o in Options(found.text).options)
    detail = client.get(result_link(found.text, identity))
    assert detail.status_code == 200 and Links(detail.text).active == []
    assert "script-src" not in found.headers["content-security-policy"]


@pytest.mark.parametrize(
    "path",
    [
        "/web/knowledge",
        "/web/knowledge-favorites",
        "/web/knowledge-removed",
        "/web/knowledge/IDENTITY",
        "/web/knowledge-removed/IDENTITY",
    ],
)
@pytest.mark.parametrize("condition", ["long", "newline", "duplicate"])
def test_invalid_topic_conditions_are_rejected_on_all_browse_surfaces(
    setup, path, condition
):
    _, client, _, _, identity = setup
    value = "字" * 121 if condition == "long" else "a\nb"
    query = (
        [("topic", "one"), ("topic", "two")]
        if condition == "duplicate"
        else {"topic": value}
    )
    result = client.get(path.replace("IDENTITY", identity), params=query)
    assert result.status_code == 400


def test_guest_and_read_failure_are_safe_and_do_not_expose_internal_paths(
    setup, monkeypatch
):
    _, client, repo, _, _ = setup
    client.cookies.clear()
    assert client.get("/web/knowledge", follow_redirects=False).status_code == 303
    login(client)

    def broken(*a, **k):
        raise sqlite3.OperationalError("private path and data")

    monkeypatch.setattr(type(repo), "knowledge_topics", broken)
    result = client.get("/web/knowledge")
    assert result.status_code == 503 and "private path" not in result.text
