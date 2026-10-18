import sqlite3
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4

import pytest

from tests import test_web_lesson_revision as base
from tests import test_web_booklets as book_tests
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import login, Forms

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.active = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag in {"script", "iframe", "img"} or any(
            name.startswith("on") for name in attrs
        ):
            self.active.append(tag)


def result_link(text, identity):
    return next(
        url
        for url in Links(text).links
        if url.startswith("/web/knowledge/" + identity + "?")
    )


def test_body_search_preview_highlights_context_and_returns_to_same_results_without_writes(
    setup,
):
    _, client, repo, user, _ = setup
    identity = saved_lesson(
        repo,
        user.user_id,
        title="表达训练",
        content="## 方法\n先观点后举例。" + "\n学习要用具体例子。" * 7,
    )
    before = repo.database_path.read_bytes()
    found = client.get("/web/knowledge", params={"q": "具体例子"})
    assert found.status_code == 200 and "表达训练" in found.text
    assert "匹配：正文" in found.text and "<mark>具体例子</mark>" in found.text
    target = result_link(found.text, identity)
    detail = client.get(target)
    assert (
        detail.status_code == 200
        and "当前正文共 7 处匹配" in detail.text
        and "展示 5 段附近原文" in detail.text
    )
    assert "在对话中重温" in detail.text and "修改教案" in detail.text
    back = next(
        url for url in Links(detail.text).links if url.startswith("/web/knowledge?")
    )
    assert parse_qs(urlsplit(back).query) == {
        "q": ["具体例子"],
        "status": ["saved"],
        "page": ["1"],
    }
    assert repo.database_path.read_bytes() == before


def test_title_only_and_stale_query_show_current_text_without_fabricated_hits(setup):
    _, client, repo, user, identity = setup
    found = client.get("/web/knowledge", params={"q": "原版教案"})
    detail = client.get(result_link(found.text, identity))
    assert "匹配：标题" in found.text and "当前正文没有匹配文字" in detail.text
    repo.revise_knowledge(
        user.user_id, identity, 1, title="新版标题", content="已经修订的全文。"
    )
    current = client.get(f"/web/knowledge/{identity}", params={"find": "最初的例子"})
    assert "当前正文没有匹配文字" in current.text and "已经修订的全文" in current.text
    assert "<mark>最初的例子</mark>" not in current.text


def test_saved_and_pending_results_do_not_confirm_or_include_dismissed_assets(setup):
    _, client, repo, user, _ = setup
    discarded = saved_lesson(
        repo, user.user_id, title="放弃的标题", content="独特草稿正文。", save=False
    )
    repo.confirm_knowledge(user.user_id, discarded, save=False)
    draft = saved_lesson(
        repo, user.user_id, title="仅草稿有的标题", content="独特草稿正文。", save=False
    )
    saved = client.get("/web/knowledge", params={"q": "独特草稿正文"})
    assert "没有找到匹配内容" in saved.text and "仅草稿有的标题" not in saved.text
    pending = client.get(
        "/web/knowledge", params={"q": "独特草稿正文", "status": "pending"}
    )
    assert "仅草稿有的标题" in pending.text and "放弃的标题" not in pending.text
    detail = client.get(result_link(pending.text, draft))
    assert "确认保存到知识库" in detail.text
    assert "status=pending" in detail.text
    assert repo.knowledge(user.user_id, draft)["status"] == "pending"


def test_account_isolation_and_login_are_enforced_for_lookup_and_context(setup):
    _, client, repo, user, identity = setup
    repo.revise_knowledge(
        user.user_id,
        identity,
        1,
        title="私人的标题不可泄露",
        content="共同查询词但仅本人可读。",
    )
    client.cookies.clear()
    login(client, "two@example.com")
    found = client.get("/web/knowledge", params={"q": "共同查询词"})
    assert "私人的标题不可泄露" not in found.text and "没有找到匹配内容" in found.text
    assert client.get(f"/web/knowledge/{identity}?find=共同查询词").status_code == 404
    client.cookies.clear()
    assert (
        client.get("/web/knowledge?q=共同查询词", follow_redirects=False).status_code
        == 303
    )


def test_query_and_original_markup_are_escaped_in_snippets_and_context(setup):
    _, client, repo, user, _ = setup
    query = "<img src=x onerror=alert(1)>"
    identity = saved_lesson(
        repo,
        user.user_id,
        title="安全标题",
        content="原文：" + query + "<script>alert(1)</script> & 其他文字。",
    )
    found = client.get("/web/knowledge", params={"q": query})
    assert "<mark>&lt;img src=x onerror=alert(1)&gt;</mark>" in found.text
    assert Links(found.text).active == []
    detail = client.get(result_link(found.text, identity))
    assert Links(detail.text).active == [] and "&lt;script&gt;" in detail.text
    assert detail.headers["cache-control"] == "no-store"


def test_booklet_candidates_match_body_and_return_to_original_collection_search(setup):
    _, client, repo, user, identity = setup
    repo.revise_knowledge(
        user.user_id,
        identity,
        1,
        title="不含关键词的标题",
        content="这份正文讲具体例子如何帮助理解。",
    )
    book, _ = book_tests.create(client, "正文查找手册")
    candidates = client.get(f"/web/booklets/{book}/edit", params={"q": "具体例子"})
    assert (
        "匹配：正文" in candidates.text and "<mark>具体例子</mark>" in candidates.text
    )
    detail = client.get(result_link(candidates.text, identity))
    back = next(
        url
        for url in Links(detail.text).links
        if url.startswith(f"/web/booklets/{book}/edit?")
    )
    assert "返回手册收录结果" in detail.text and parse_qs(urlsplit(back).query)[
        "q"
    ] == ["具体例子"]
    path = f"/web/booklets/{book}/add"
    fields = Forms(candidates.text).values(path)
    saved = client.post(path, data=fields)
    assert saved.status_code == 200 and "q=%E5%85%B7%E4%BD%93%E4%BE%8B%E5%AD%90" in str(
        saved.url
    )
    assert repo.booklet(user.user_id, book)["chapters"][0]["knowledge_id"] == identity
    assert repo.booklet(user.user_id, book)["reading_position"]["revision"] == 0


def test_search_results_paginate_and_keep_query_status_and_back_page(setup):
    _, client, repo, user, _ = setup
    with sqlite3.connect(repo.database_path) as db:
        db.executemany(
            "INSERT INTO coach_knowledge VALUES(?,?,?,'查找分页教案','主题','分页独有内容','[]','saved',?,1000)",
            [(uuid4().hex, user.user_id, 9000 + i, 3000 + i) for i in range(23)],
        )
    first = client.get("/web/knowledge", params={"q": "分页独有内容"})
    next_url = next(
        url
        for url in Links(first.text).links
        if "page=2" in url and url.startswith("?")
    )
    second = client.get("/web/knowledge" + next_url)
    assert second.status_code == 200 and second.text.count('class="library-item"') == 3
    target = next(
        url
        for url in Links(second.text).links
        if url.startswith("/web/knowledge/") and "find=" in url
    )
    detail = client.get(target)
    back = next(
        url for url in Links(detail.text).links if url.startswith("/web/knowledge?")
    )
    assert parse_qs(urlsplit(back).query)["page"] == ["2"]


@pytest.mark.parametrize(
    "params",
    [
        {"q": "字" * 121},
        {"q": "a\x00b"},
        {"q": "a\nb"},
        {"page": "bad"},
        {"status": "dismissed"},
    ],
)
def test_invalid_lookup_inputs_fail_without_mutating_content(setup, params):
    _, client, repo, _, _ = setup
    before = repo.database_path.read_bytes()
    assert client.get("/web/knowledge", params=params).status_code == 400
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize(
    "params",
    [
        {"find": "字" * 121},
        {"find": "a\x00b"},
        {"result_page": "0"},
        {"result_page": "1000001"},
        {"booklet": "../../evil"},
    ],
)
def test_invalid_context_parameters_are_rejected(setup, params):
    _, client, _, _, identity = setup
    assert client.get(f"/web/knowledge/{identity}", params=params).status_code == 400


def test_foreign_booklet_cannot_be_used_as_a_return_target(setup):
    _, client, repo, _, identity = setup
    book = uuid4().hex
    repo.create_booklet("other-account", book, "其他人私有手册")
    detail = client.get(
        f"/web/knowledge/{identity}", params={"find": "例子", "booklet": book}
    )
    assert detail.status_code == 404 and "其他人私有手册" not in detail.text
