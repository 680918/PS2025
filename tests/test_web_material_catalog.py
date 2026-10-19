import re
import sqlite3
from contextlib import closing
from html import escape
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from tests import test_web_library as library_tests
from tests.test_web_coach_dialogue import Forms, add_user, login, form, BASE

setup = library_tests.setup
password_hash = library_tests.password_hash
no_real_services = library_tests.no_real_services


def seed(directory, user):
    repo = MaterialRepository(directory / "coach_library.db")
    ids = [
        repo.add(user.user_id, filename, text.encode(), title=title, pasted=pasted)
        for filename, text, title, pasted in [
            ("Original-READING.md", "# 原文\n回想再实践。", "阅读与行动", False),
            ("memo.txt", "理解后再应用。", "课堂笔记", True),
            ("daily.txt", "每天做一点。", "每日练习", False),
        ]
    ]
    repo.add("other", "private.txt", b"secret other", title="另一人的秘密")
    return repo, ids


def cards(html):
    return re.findall(r'<article class="library-item">(.*?)</article>', html, re.S)


def test_catalog_capacity_filters_and_empty_results_only_use_own_metadata(setup):
    _, client, user, calls, directory = setup
    repo, ids = seed(directory, user)
    login(client)
    response = client.get("/web/materials")
    assert "已保存 3 / 20 份" in response.text and "50.00 MB" in response.text
    assert "另一人的秘密" not in response.text and len(cards(response.text)) == 3
    for query, expected in (
        ({"name": "reading"}, ids[0]),
        ({"kind": "paste"}, ids[1]),
        ({"name": "每日", "kind": "txt"}, ids[2]),
    ):
        filtered = client.get("/web/materials", params=query)
        assert len(cards(filtered.text)) == 1 and expected in cards(filtered.text)[0]
        assert "已保存 3 / 20 份" in filtered.text
    empty = client.get("/web/materials?name=missing")
    assert "没有符合条件" in empty.text and not cards(empty.text)
    assert "查看全部" in empty.text
    assert len(repo.list(user.user_id)) == 3 and calls == []


@pytest.mark.parametrize(
    "query",
    [
        "kind=exe",
        "name=a&name=b",
        "kind=txt&kind=md",
        "name=" + "a" * 121,
        "name=bad%00name",
    ],
)
def test_invalid_filters_are_rejected(setup, query):
    _, client, _, calls, _ = setup
    login(client)
    assert client.get("/web/materials?" + query).status_code == 400
    assert calls == []


def test_rename_keeps_filter_and_learning_position_and_does_not_rewrite_citations(
    setup,
):
    _, client, user, calls, directory = setup
    materials, ids = seed(directory, user)
    identity = ids[0]
    dialogue = CoachRepository(
        directory / "coach_conversations.db", materials=materials
    )
    dialogue.save_book_unit(user.user_id, identity, "a" * 32, "阅读入门", 1, 1, 0)
    login(client)
    preview = client.get("/web/materials/" + identity)
    path = f"/web/materials/{identity}/study"
    client.post(path, data=Forms(preview.text).values(path))
    client.post(
        "/web/coach/message",
        data={**form(client), "message": "帮我把原文回想实践整理成教案"},
    )
    before = dialogue.topic_part(user.user_id)
    topics = dialogue.list_topics(user.user_id)
    knowledge = dialogue.list_knowledge(user.user_id, status="pending")
    assert len(knowledge) == 1 and len(dialogue.book_units(user.user_id, identity)) == 1
    assert calls[0]["sources"][0]["title"] == "阅读与行动"
    with closing(sqlite3.connect(dialogue.database_path)) as db:
        dump_before = list(db.iterdump())
    path = f"/web/materials/{identity}/edit"
    editor = client.get(path, params={"name": "READING", "kind": "md"})
    values = Forms(editor.text).values(path)
    response = client.post(
        path, data={**values, "title": "新的阅读名称"}, follow_redirects=False
    )
    assert response.status_code == 303
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query == {"name": ["READING"], "kind": ["md"], "notice": ["renamed"]}
    assert "新的阅读名称" in client.get(response.headers["location"]).text
    assert dialogue.topic_part(user.user_id) == before
    assert dialogue.list_topics(user.user_id) == topics
    assert dialogue.list_knowledge(user.user_id, status="pending") == knowledge
    with closing(sqlite3.connect(dialogue.database_path)) as db:
        assert list(db.iterdump()) == dump_before
    assert "新的阅读名称" in client.get("/web/welcome").text
    assert "新的阅读名称" in client.get(f"/web/materials/{identity}/plan").text
    assert materials.get(user.user_id, identity)["filename"] == "Original-READING.md"
    assert len(calls) == 1


def test_stale_editor_preserves_input_and_requires_explicit_resubmit(setup):
    _, client, user, calls, directory = setup
    repo, ids = seed(directory, user)
    path = f"/web/materials/{ids[0]}/edit"
    login(client)
    original = Forms(client.get(path).text).values(path)
    repo.rename(user.user_id, ids[0], "另外页面的新名称", expected_title="阅读与行动")
    response = client.post(path, data={**original, "title": "本次想用的名称"})
    assert response.status_code == 409 and "名称已在其他页面更新" in response.text
    assert repo.get(user.user_id, ids[0])["title"] == "另外页面的新名称"
    values = Forms(response.text).values(path)
    assert (
        values["title"] == "本次想用的名称"
        and values["expected_title"] == "另外页面的新名称"
    )
    assert client.post(path, data=values).status_code == 200
    assert repo.get(user.user_id, ids[0])["title"] == "本次想用的名称"
    assert calls == []


def test_invalid_title_is_kept_escaped_for_correction(setup):
    _, client, user, calls, directory = setup
    repo, ids = seed(directory, user)
    path = f"/web/materials/{ids[0]}/edit"
    login(client)
    values = Forms(client.get(path).text).values(path)
    title = '<script>alert("name")</script>\n'
    response = client.post(path, data={**values, "title": title})
    assert response.status_code == 400 and "1 至 120 字" in response.text
    assert (
        escape(title, quote=True) in response.text and "<script>" not in response.text
    )
    assert repo.get(user.user_id, ids[0])["title"] == "阅读与行动"
    assert calls == []


def test_account_csrf_origin_and_database_failure_protections(
    setup, password_hash, monkeypatch
):
    app, client, user, calls, directory = setup
    repo, ids = seed(directory, user)
    path = f"/web/materials/{ids[0]}/edit"
    assert client.get(path, follow_redirects=False).status_code == 303
    assert client.post(path, data={}, follow_redirects=False).status_code == 303
    login(client)
    values = Forms(client.get(path).text).values(path)
    for data, headers in (
        ({**values, "csrf": "bad"}, {}),
        (values, {"Origin": "https://evil.example"}),
        (values, {"Sec-Fetch-Site": "cross-site"}),
    ):
        assert client.post(path, data=data, headers=headers).status_code == 403
    second = f"/web/materials/{ids[1]}/edit"
    assert client.post(second, data=values).status_code == 403
    add_user(directory, password_hash, "two@example.com", "另一人")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        assert other.get(path).status_code == 404
        own = repo.list("other")[0]["material_id"]
        assert other.get(f"/web/materials/{own}/edit").status_code == 404
        assert other.post(path, data=values).status_code == 403
    assert repo.get(user.user_id, ids[0])["title"] == "阅读与行动"

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("private DB details")

    monkeypatch.setattr(MaterialRepository, "rename", broken)
    result = client.post(path, data=values)
    assert result.status_code == 503 and "private DB details" not in result.text
    assert result.headers["cache-control"] == "no-store"
    assert calls == []
