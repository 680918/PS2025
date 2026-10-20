import sqlite3
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from conversation.coach_repository import CoachRepository
from tests import test_web_booklets as base
from tests.test_booklet_find import make_book
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def result_links(response):
    return [
        link
        for link in Links(response.text).links
        if "?lesson=" in link and "#booklet-reading" in link
    ]


def test_find_read_navigation_and_back_preserve_query_and_reading_position(setup):
    _, client, repo, user, first = setup
    second = saved_lesson(
        repo, user.user_id, title="第二章", content="这里有关键词与例子"
    )
    book = make_book(repo, user.user_id, [first, second])
    repo.remember_booklet_position(user.user_id, book, 3, first, 0)
    before = repo.database_path.read_bytes()
    reading = client.get(f"/web/booklets/{book}")
    assert f"/web/booklets/{book}/find" in reading.text
    found = client.get(f"/web/booklets/{book}/find", params={"q": "关键词"})
    assert found.status_code == 200 and "<mark>关键词</mark>" in found.text
    link = result_links(found)[0]
    assert parse_qs(urlsplit(link).query)["lesson"] == [second]
    opened = client.get(link)
    assert "这里有关键词与例子" in opened.text and "返回本册查找结果" in opened.text
    assert "<mark>关键词</mark>" in opened.text
    back = next(x for x in Links(opened.text).links if "/find?" in x)
    assert parse_qs(urlsplit(back).query) == {"q": ["关键词"], "page": ["1"]}
    chapter_links = [x for x in Links(opened.text).links if x.startswith("?lesson=")]
    assert chapter_links and all(
        "find=" in x and "find_page=1" in x for x in chapter_links
    )
    assert repo.database_path.read_bytes() == before
    for response in [found, opened]:
        assert response.headers["cache-control"] == "no-store"
        assert Links(response.text).active == []


def test_second_page_and_current_version_stable_open_after_reorder_and_removal(setup):
    _, client, repo, user, _ = setup
    ids = [
        saved_lesson(repo, user.user_id, title=f"教案{n}", content="共同关键词")
        for n in range(21)
    ]
    book = make_book(repo, user.user_id, ids)
    found = client.get(f"/web/booklets/{book}/find?q=关键词&page=2")
    assert len(result_links(found)) == 1 and "第 21 章" in found.text
    link = result_links(found)[0]
    repo.change_booklet(user.user_id, book, 22, "up", knowledge_id=ids[-1])
    repo.revise_knowledge(
        user.user_id, ids[-1], 1, title="新版教案", content="已经换了内容"
    )
    opened = client.get(link)
    assert "第 20 章 /" in opened.text and "新版教案" in opened.text
    assert "当前未匹配关键词" in opened.text and "find_page=2" in opened.text
    repo.change_booklet(user.user_id, book, 23, "remove", knowledge_id=ids[-1])
    missing = client.get(link)
    assert missing.status_code == 404 and "已不在本手册" in missing.text
    assert "page=2" in missing.text and "已经换了内容" not in missing.text


def test_html_matches_are_inert_and_search_does_not_include_citations(setup):
    _, client, repo, user, first = setup
    evil = "<img src=x onerror=alert(1)>"
    identity = saved_lesson(
        repo, user.user_id, title="<script>恶意标题</script>", content=evil
    )
    book = make_book(
        repo, user.user_id, [first, identity], title="<script>手册</script>"
    )
    found = client.get(f"/web/booklets/{book}/find", params={"q": evil})
    assert found.status_code == 200 and "<mark>&lt;img" in found.text
    assert Links(found.text).active == []
    assert (
        client.get(f"/web/booklets/{book}/find?q=原始依据").text.find("找到 0 个章节")
        >= 0
    )
    assert "找不到" not in found.text


def test_guest_and_other_account_cannot_search_or_open_owned_results(setup):
    app, client, repo, user, first = setup
    book = make_book(repo, user.user_id, [first], title="PRIVATE_BOOK_TITLE")
    with TestClient(app, base_url=BASE) as other:
        assert (
            other.get(
                f"/web/booklets/{book}/find?q=例子", follow_redirects=False
            ).status_code
            == 303
        )
        login(other, "two@example.com")
        for path in [
            f"/web/booklets/{book}/find?q=例子",
            f"/web/booklets/{book}?lesson={first}&find=例子",
        ]:
            response = other.get(path)
            assert (
                response.status_code == 404
                and "PRIVATE_BOOK_TITLE" not in response.text
            )


@pytest.mark.parametrize(
    "suffix",
    [
        "?q=a&q=b",
        "?page=0",
        "?page=10001",
        "?q=" + ("x" * 121),
        "?user_id=other",
        "?q=x%0Ay",
    ],
)
def test_invalid_find_parameters_are_rejected(setup, suffix):
    _, client, repo, user, first = setup
    book = make_book(repo, user.user_id, [first])
    assert client.get(f"/web/booklets/{book}/find" + suffix).status_code == 400


@pytest.mark.parametrize(
    "suffix",
    [
        "?lesson=x",
        "?lesson=" + ("a" * 32) + "&chapter=1",
        "?find=a&find=b",
        "?find_page=0",
    ],
)
def test_invalid_read_context_does_not_select_another_chapter(setup, suffix):
    _, client, repo, user, first = setup
    book = make_book(repo, user.user_id, [first])
    assert client.get(f"/web/booklets/{book}" + suffix).status_code == 400


def test_database_failure_does_not_leak_internal_details(setup, monkeypatch):
    _, client, repo, user, first = setup
    book = make_book(repo, user.user_id, [first])

    def broken(*a, **k):
        raise sqlite3.OperationalError("SECRET_PATH")

    monkeypatch.setattr(CoachRepository, "find_booklet", broken)
    response = client.get(f"/web/booklets/{book}/find?q=例子")
    assert response.status_code == 503 and "SECRET_PATH" not in response.text
