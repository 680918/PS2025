from urllib.parse import urlencode
from uuid import uuid4
from zipfile import ZipFile
import io

import pytest

from tests import test_web_lesson_revision as base_tests
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import Forms, login

setup = base_tests.setup
password_hash = base_tests.password_hash
no_real_services = base_tests.no_real_services


def create(client, title="<我的学习手册>"):
    fields = Forms(client.get("/web/booklets/new").text).values("/web/booklets/new")
    result = client.post("/web/booklets/new", data={**fields, "title": title})
    assert result.status_code == 200
    return fields["identity"], result


def member_fields(client, book, operation, lesson):
    page = client.get(f"/web/booklets/{book}/edit")
    path = f"/web/booklets/{book}/{operation}"
    return next(
        form["values"]
        for form in Forms(page.text).forms
        if form["path"] == path and form["values"].get("knowledge_id") == lesson
    )


def add(client, book, lesson):
    path = f"/web/booklets/{book}/add"
    return client.post(path, data=member_fields(client, book, "add", lesson))


def test_create_collect_reorder_read_remove_and_export_without_ai(setup):
    _, client, repo, user, first = setup
    second = saved_lesson(
        repo, user.user_id, title="第二教案", content="第二章独有正文。"
    )
    book, page = create(client)
    assert "&lt;我的学习手册&gt;" in page.text
    assert add(client, book, first).status_code == 200
    assert add(client, book, second).status_code == 200
    reading = client.get(f"/web/booklets/{book}")
    assert reading.status_code == 200 and "最初的例子" in reading.text
    assert "第二章独有正文" not in reading.text
    down = member_fields(client, book, "down", first)
    assert client.post(f"/web/booklets/{book}/down", data=down).status_code == 200
    assert "第二章独有正文" in client.get(f"/web/booklets/{book}").text
    md = client.get(f"/web/booklets/{book}/download?format=md")
    html = client.get(f"/web/booklets/{book}/download?format=html")
    assert md.status_code == html.status_code == 200
    assert md.text.index("第二教案") < md.text.index("原版教案")
    assert "原始依据" in md.text and "第 1 版" in html.text
    assert "attachment;" in md.headers["content-disposition"]
    remove = member_fields(client, book, "remove", first)
    assert client.post(f"/web/booklets/{book}/remove", data=remove).status_code == 200
    assert repo.knowledge(user.user_id, first, saved_only=True)
    assert add(client, book, first).status_code == 200
    export_page = client.get("/web/export")
    assert "学习手册" in export_page.text
    csrf = Forms(export_page.text).values("/web/export")["csrf"]
    downloaded = client.post(
        "/web/export", data={"csrf": csrf, "period": "all", "scope": ["booklets"]}
    )
    assert downloaded.status_code == 200
    with ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert any(
            name.startswith("学习手册/") and name.endswith(".html")
            for name in archive.namelist()
        )


def test_old_editor_preserves_title_and_cannot_overwrite_membership(setup):
    _, client, repo, user, lesson = setup
    book, _ = create(client)
    path = f"/web/booklets/{book}/title"
    old = Forms(client.get(f"/web/booklets/{book}/edit").text).values(path)
    assert add(client, book, lesson).status_code == 200
    conflict = client.post(path, data={**old, "title": "保留我的新名称"})
    assert conflict.status_code == 409 and "另一页面" in conflict.text
    retry = Forms(conflict.text).values(path)
    assert retry["title"] == "保留我的新名称" and retry["revision"] == "2"
    assert client.post(path, data=retry).status_code == 200
    saved = repo.booklet(user.user_id, book)
    assert saved["title"] == "保留我的新名称" and len(saved["chapters"]) == 1


def test_latest_lesson_revision_and_original_review_are_used(setup):
    _, client, repo, user, lesson = setup
    book, _ = create(client)
    add(client, book, lesson)
    repo.revise_knowledge(
        user.user_id, lesson, 1, title="最新版章节", content="最新正文内容。"
    )
    path = f"/web/booklets/{book}"
    page = client.get(path)
    assert (
        "最新版章节" in page.text
        and "第 2 版" in page.text
        and "最新正文内容" in page.text
    )
    review_path = f"/web/knowledge/{lesson}/review"
    values = Forms(page.text).values(review_path)
    assert client.post(review_path, data=values).status_code == 200
    assert repo.review(user.user_id)["content"] == "最新正文内容。"
    assert "最新正文内容" in client.get(path + "/download?format=md").text


@pytest.mark.parametrize(
    "bad",
    [
        "csrf",
        "revision",
        "lesson",
        "foreign",
        "draft",
        "origin",
        "cross-site",
        "duplicate",
        "extra",
        "json",
        "oversize",
    ],
)
def test_bad_membership_requests_do_not_change_booklet(setup, bad):
    _, client, repo, user, lesson = setup
    draft = saved_lesson(repo, user.user_id, title="待确认草稿", save=False)
    book, _ = create(client)
    path = f"/web/booklets/{book}/add"
    fields = member_fields(client, book, "add", lesson)
    headers = {}
    if bad == "csrf":
        fields["csrf"] = "0" * 64
    if bad == "revision":
        fields["revision"] = "2"
    if bad == "lesson":
        fields["knowledge_id"] = uuid4().hex
    if bad == "origin":
        headers["origin"] = "https://evil.example"
    if bad == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    if bad == "extra":
        fields["owner"] = user.user_id
    if bad == "oversize":
        fields["q"] = "字" * 9000
    if bad == "draft":
        # The saved lesson changes status after a legitimate form was rendered.
        fields = member_fields(client, book, "add", lesson)
        import sqlite3

        with sqlite3.connect(repo.database_path) as db:
            db.execute(
                "UPDATE coach_knowledge SET status='pending' WHERE knowledge_id=?",
                (lesson,),
            )
    if bad == "foreign":
        client.cookies.clear()
        login(client, "two@example.com")
    if bad == "duplicate":
        result = client.post(
            path,
            content=urlencode(fields) + "&revision=1",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    elif bad == "json":
        result = client.post(path, json=fields)
    else:
        result = client.post(path, data=fields, headers=headers)
    assert result.status_code in {400, 403, 404}
    assert repo.booklet(user.user_id, book)["chapters"] == []
    assert repo.knowledge(user.user_id, draft)["status"] == "pending"


def test_account_boundary_and_same_origin_opaque_form(setup):
    _, client, repo, user, lesson = setup
    book, _ = create(client)
    fields = member_fields(client, book, "add", lesson)
    path = f"/web/booklets/{book}/add"
    assert (
        client.post(
            path,
            data=fields,
            headers={"origin": "null", "sec-fetch-site": "same-origin"},
        ).status_code
        == 200
    )
    client.cookies.clear()
    login(client, "two@example.com")
    for suffix in ("", "/edit", "/download?format=html"):
        assert client.get(f"/web/booklets/{book}" + suffix).status_code == 404
    assert "&lt;我的学习手册&gt;" not in client.get("/web/booklets").text
    client.cookies.clear()
    assert client.get("/web/booklets", follow_redirects=False).status_code == 303


def test_search_is_preserved_and_create_replay_does_not_duplicate(setup):
    _, client, repo, user, lesson = setup
    fields = Forms(client.get("/web/booklets/new").text).values("/web/booklets/new")
    fields["title"] = "Python 学习册"
    assert client.post("/web/booklets/new", data=fields).status_code == 200
    assert client.post("/web/booklets/new", data=fields).status_code == 200
    assert len(repo.list_booklets(user.user_id)) == 1
    book = fields["identity"]
    page = client.get(f"/web/booklets/{book}/edit?q=原版")
    operation = f"/web/booklets/{book}/add"
    values = Forms(page.text).values(operation)
    result = client.post(operation, data=values)
    assert result.status_code == 200 and "q=%E5%8E%9F%E7%89%88" in str(result.url)
    assert "Python 学习册" in client.get("/web/booklets?q=Python").text
    assert "Python 学习册" not in client.get("/web/booklets?q=无此名称").text
    assert client.get(f"/web/booklets/{book}?chapter=0").status_code == 404
