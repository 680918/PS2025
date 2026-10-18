import sqlite3
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from tests import test_web_book_section as base
from tests.test_web_coach_dialogue import BASE, Forms, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def hit_links(text):
    return [url for url in Links(text).links if url.endswith("#material-find")]


def test_find_original_then_choose_and_explain_exact_chunk_in_same_chat(setup):
    _, client, repo, materials, user, _, _, calls = setup
    book = materials.add(
        user.user_id,
        "learning.txt",
        ("甲" * 1100 + "具体例子能帮助理解" + "乙" * 1200).encode(),
        title="我的阅读",
    )
    before = {
        path: path.read_bytes()
        for path in (repo.database_path, materials.database_path)
    }
    found = client.get("/web/materials/find", params={"q": "具体例子"})
    assert found.status_code == 200 and "我的阅读" in found.text
    assert "<mark>具体例子</mark>" in found.text
    target = hit_links(found.text)[0]
    assert parse_qs(urlsplit(target).query)["part"] == ["2"]
    preview = client.get(target)
    assert preview.status_code == 200 and "关键词附近原文" in preview.text
    assert "本片段有 1 处匹配" in preview.text
    assert "选中这段，回到对话" in preview.text
    assert calls == [] and repo.list_topics(user.user_id) == []
    assert all(path.read_bytes() == old for path, old in before.items())
    form = Forms(preview.text).values(f"/web/materials/{book}/study")
    selected = client.post(f"/web/materials/{book}/study", data=form)
    assert selected.status_code == 200 and calls == []
    assert repo.topic_part(user.user_id)["chunk_id"] == form["chunk_id"]
    message = Forms(selected.text).values("/web/coach/message", "study")
    assert client.post("/web/coach/message", data=message).status_code == 200
    assert len(calls) == 1 and len(calls[0]["sources"]) == 1
    assert calls[0]["sources"][0]["source_id"] == form["chunk_id"]
    assert "具体例子" in calls[0]["sources"][0]["excerpt"]


def test_scope_pagination_back_and_adjacent_navigation_retain_query(setup):
    _, client, _, materials, user, _, _, calls = setup
    book = materials.add(
        user.user_id,
        "many.txt",
        (("查找词" + "甲" * 797) * 25).encode(),
        title="有很多片段",
    )
    materials.add(
        user.user_id,
        "elsewhere.txt",
        "查找词但属于另一份资料".encode(),
        title="另一份资料",
    )
    first = client.get("/web/materials/find", params={"q": "查找词", "material": book})
    assert len(hit_links(first.text)) == 20 and "下一页 →" in first.text
    assert "另一份资料</h2>" not in first.text
    next_page = next(link for link in Links(first.text).links if "page=2" in link)
    second = client.get(next_page)
    assert len(hit_links(second.text)) == 5 and "下一页 →" not in second.text
    target = hit_links(second.text)[0]
    preview = client.get(target)
    back = next(
        link
        for link in Links(preview.text).links
        if link.startswith("/web/materials/find?")
    )
    assert parse_qs(urlsplit(back).query) == {
        "q": ["查找词"],
        "material": [book],
        "page": ["2"],
    }
    adjacent = next(
        link for link in Links(preview.text).links if link.startswith("?part=22")
    )
    assert parse_qs(urlsplit(adjacent).query)["find_page"] == ["2"]
    locator = Forms(preview.text).values("/web/materials/" + book)
    assert locator["find"] == "查找词" and locator["find_material"] == book
    assert calls == []


def test_lookup_and_context_preserve_existing_selected_topic_and_part(setup):
    _, client, repo, materials, user, _, book, calls = setup
    base.choose(client, book, 1)
    old = repo.topic_part(user.user_id)
    another = materials.add(
        user.user_id, "different.txt", "与当前学习无关的查找词".encode()
    )
    found = client.get("/web/materials/find", params={"q": "查找词"})
    preview = client.get(hit_links(found.text)[0])
    assert preview.status_code == 200 and another in hit_links(found.text)[0]
    assert repo.topic_part(user.user_id) == old and calls == []


def test_login_and_account_isolation_cover_search_filters_and_preview(setup):
    app, client, _, materials, user, _, book, calls = setup
    materials.add(
        user.user_id, "onlymine.txt", "仅本人的原文暗号".encode(), title="私有书名"
    )
    with TestClient(app, base_url=BASE) as other:
        assert (
            other.get(
                "/web/materials/find?q=原文暗号", follow_redirects=False
            ).status_code
            == 303
        )
        login(other, "two@example.com")
        found = other.get("/web/materials/find?q=原文暗号")
        assert "私有书名" not in found.text and "没有找到匹配原文" in found.text
        filtered = other.get(
            "/web/materials/find", params={"q": "甲", "material": book}
        )
        assert filtered.status_code == 404 and "书籍标题" not in filtered.text
        assert other.get(f"/web/materials/{book}?find=甲").status_code == 404
    assert calls == []


def test_query_and_raw_source_markup_are_safe_in_results_and_preview(setup):
    _, client, _, materials, user, _, _, calls = setup
    query = '<img src=x onerror="alert(1)">'
    materials.add(
        user.user_id,
        "unsafe.txt",
        (query + "<script>alert(2)</script> & 正文").encode(),
        title='</title><iframe src="/">',
    )
    found = client.get("/web/materials/find", params={"q": query})
    preview = client.get(hit_links(found.text)[0])
    for response in (found, preview):
        assert response.status_code == 200
        assert Links(response.text).active == []
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert (
            "<mark>&lt;img src=x onerror=&quot;alert(1)&quot;&gt;</mark>"
            in response.text
        )
    assert calls == []


@pytest.mark.parametrize(
    "title",
    [
        "</title><script>alert(1)</script>",
        '<img src=x onerror="alert(2)">',
        "资料 & 成长 <笔记>",
    ],
)
def test_shared_document_title_is_text_even_when_a_saved_name_contains_markup(title):
    from html import escape
    from api.public_pages import _render_layout

    rendered = _render_layout(title, "<main>安全正文</main>", signed_in=True)
    assert "<title>" + escape(title) + "</title>" in rendered
    assert rendered.count("</title>") == 1
    assert Links(rendered).active == []


def test_pdf_hits_use_actual_third_page_and_do_not_claim_blank_page_is_readable(setup):
    _, client, _, materials, user, _, _, calls = setup
    book = materials.add(user.user_id, "pdf.pdf", base.pdf_with_blank_middle())
    found = client.get("/web/materials/find", params={"q": "Spaced", "material": book})
    assert len(hit_links(found.text)) == 2 and "PDF 第 2 页" not in found.text
    preview = client.get(hit_links(found.text)[1])
    assert "PDF 第 3 页 · 片段 2" in preview.text
    assert "<mark>Spaced</mark>" in preview.text and calls == []
    blank = client.get(
        f"/web/materials/{book}",
        params={"page": 2, "find": "Spaced", "find_material": book, "find_page": 2},
    )
    assert blank.status_code == 200 and "没有可提取的文字" in blank.text
    links = Links(blank.text).links
    back = next(link for link in links if link.startswith("/web/materials/find?"))
    assert parse_qs(urlsplit(back).query) == {
        "q": ["Spaced"],
        "material": [book],
        "page": ["2"],
    }
    first = next(link for link in links if link.startswith(f"/web/materials/{book}?"))
    assert parse_qs(urlsplit(first).query)["find"] == ["Spaced"]
    assert "选中这段，回到对话" not in blank.text


@pytest.mark.parametrize(
    "query",
    [
        "q=" + "x" * 121,
        "q=a%0Ab",
        "q=a%00b",
        "page=0",
        "page=10001",
        "page=1.5",
        "page=-1",
        "material=../outside",
        "q=a&q=b",
        "page=1&page=2",
        "material=a&material=b",
    ],
)
def test_malformed_lookup_is_rejected_without_mutation(setup, query):
    _, client, repo, materials, _, _, _, calls = setup
    before = [
        path.read_bytes() for path in (repo.database_path, materials.database_path)
    ]
    assert client.get("/web/materials/find?" + query).status_code == 400
    assert before == [
        path.read_bytes() for path in (repo.database_path, materials.database_path)
    ]
    assert calls == []


def test_invalid_or_nonmatching_context_is_honest_and_bounded(setup):
    _, client, _, _, _, _, book, calls = setup
    path = f"/web/materials/{book}"
    assert client.get(path + "?find=" + "x" * 121).status_code == 400
    assert client.get(path + "?find=甲&find_page=0").status_code == 400
    assert client.get(path + "?find=甲&find_material=../other").status_code == 400
    missing = client.get(path + "?find=不存在的词")
    assert "当前片段没有匹配文字" in missing.text
    assert "<mark>" not in missing.text and calls == []


def test_empty_search_and_unavailable_database_have_clear_pages(setup, monkeypatch):
    _, client, _, _, _, _, book, calls = setup
    assert "输入一个关键词" in client.get("/web/materials/find").text
    assert "查找资料原文" in client.get("/web/materials").text
    assert "查找资料原文" in client.get(f"/web/materials/{book}").text

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("private database path and internal details")

    monkeypatch.setattr(base.MaterialRepository, "find_chunks", unavailable)
    failed = client.get("/web/materials/find?q=甲")
    assert failed.status_code == 503 and "private database" not in failed.text
    assert calls == []
