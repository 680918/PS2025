import sqlite3
from urllib.parse import urlencode

import pytest

from tests import test_web_booklets as base
from tests.test_web_coach_dialogue import Forms, login
from tests.test_lesson_revision import saved_lesson

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def prepare(setup):
    _, client, repo, user, first = setup
    second = saved_lesson(
        repo, user.user_id, title="下一次续读", content="续读独有正文。"
    )
    book, _ = base.create(client)
    for lesson in (first, second):
        assert base.add(client, book, lesson).status_code == 200
    return client, repo, user, book, first, second


def position_form(client, book, chapter):
    path = f"/web/booklets/{book}/position"
    return path, Forms(
        client.get(f"/web/booklets/{book}?chapter={chapter}").text
    ).values(path)


def test_explicit_save_resume_directory_and_browsing_does_not_move_position(setup):
    client, repo, user, book, first, second = prepare(setup)
    path, fields = position_form(client, book, 2)
    assert repo.booklet(user.user_id, book)["reading_position"]["revision"] == 0
    saved = client.post(path, data=fields)
    assert saved.status_code == 200 and "已记住本章位置" in saved.text
    assert "续读独有正文" in saved.text and "最初的例子" not in saved.text
    assert "已记到第 2 章" in client.get("/web/booklets").text
    assert "继续阅读" in client.get("/web/booklets").text
    assert client.post(path, data=fields).status_code == 200
    assert "最初的例子" in client.get(f"/web/booklets/{book}?chapter=1").text
    assert "续读独有正文" in client.get(f"/web/booklets/{book}").text
    client.cookies.clear()
    login(client, "one@example.com")
    assert "续读独有正文" in client.get(f"/web/booklets/{book}").text
    move = base.member_fields(client, book, "up", second)
    client.post(f"/web/booklets/{book}/up", data=move)
    assert "已记到第 1 章" in client.get(f"/web/booklets/{book}").text
    assert (
        "已记到第 1 章" in client.get(f"/web/booklets/{book}/download?format=md").text
    )


def test_stale_tab_and_reorganized_directory_preserve_latest_position(setup):
    client, repo, user, book, first, second = prepare(setup)
    path, old = position_form(client, book, 1)
    _, second_fields = position_form(client, book, 2)
    assert client.post(path, data=second_fields).status_code == 200
    conflict = client.post(path, data=old)
    assert conflict.status_code == 409 and "没有覆盖" in conflict.text
    _, fresh = position_form(client, book, 1)
    repo.change_booklet(user.user_id, book, 3, "title", title="新名称")
    assert client.post(path, data=fresh).status_code == 409
    assert (
        repo.booklet(user.user_id, book)["reading_position"]["knowledge_id"] == second
    )


def test_removed_position_is_visible_and_replacement_is_explicit(setup):
    client, repo, user, book, first, second = prepare(setup)
    path, fields = position_form(client, book, 2)
    client.post(path, data=fields)
    remove = base.member_fields(client, book, "remove", second)
    client.post(f"/web/booklets/{book}/remove", data=remove)
    page = client.get(f"/web/booklets/{book}")
    assert "已移出或暂不可用" in page.text and "最初的例子" in page.text
    assert "已移出或暂不可用" in client.get("/web/booklets").text
    assert (
        repo.booklet(user.user_id, book)["reading_position"]["knowledge_id"] == second
    )
    _, replace = position_form(client, book, 1)
    assert client.post(path, data=replace).status_code == 200
    assert repo.booklet(user.user_id, book)["reading_position"]["knowledge_id"] == first


@pytest.mark.parametrize(
    "bad",
    [
        "csrf",
        "revision",
        "position_revision",
        "knowledge_id",
        "origin",
        "opaque-origin",
        "cross-site",
        "duplicate",
        "extra",
        "json",
        "oversize",
        "foreign",
        "draft",
    ],
)
def test_bad_position_requests_cannot_write(setup, bad):
    client, repo, user, book, first, second = prepare(setup)
    path, fields = position_form(client, book, 2)
    headers = {}
    if bad in {"csrf", "revision", "position_revision", "knowledge_id"}:
        fields[bad] = "0" * 64 if bad == "csrf" else "bad"
    elif bad == "origin":
        headers["origin"] = "https://evil.example"
    elif bad == "opaque-origin":
        headers["origin"] = "null"
    elif bad == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    elif bad == "extra":
        fields["owner"] = user.user_id
    elif bad == "oversize":
        fields["csrf"] = "x" * 9000
    elif bad == "foreign":
        client.cookies.clear()
        login(client, "two@example.com")
    elif bad == "draft":
        with sqlite3.connect(repo.database_path) as db:
            db.execute(
                "UPDATE coach_knowledge SET status='pending' WHERE knowledge_id=?",
                (second,),
            )
    if bad == "duplicate":
        response = client.post(
            path,
            content=urlencode(fields) + "&position_revision=0",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    elif bad == "json":
        response = client.post(path, json=fields)
    else:
        response = client.post(path, data=fields, headers=headers)
    assert response.status_code in {400, 403, 404}
    assert repo.booklet(user.user_id, book)["reading_position"]["revision"] == 0


def test_position_is_bound_to_book_and_login_and_same_origin_is_accepted(setup):
    client, repo, user, book, first, second = prepare(setup)
    path, fields = position_form(client, book, 2)
    other, _ = base.create(client, "另一本")
    base.add(client, other, second)
    assert (
        client.post(f"/web/booklets/{other}/position", data=fields).status_code == 403
    )
    assert (
        client.post(
            path,
            data=fields,
            headers={"origin": "null", "sec-fetch-site": "same-origin"},
        ).status_code
        == 200
    )
    client.cookies.clear()
    assert client.post(path, data=fields, follow_redirects=False).status_code == 303
    assert repo.booklet(user.user_id, other)["reading_position"]["revision"] == 0
