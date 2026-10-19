import secrets
import sqlite3
from html import escape

import pytest
from fastapi.testclient import TestClient

from coach.learning_topics import topic_edit_version
from conversation.coach_repository import CoachRepository
from tests import test_web_studies as base_tests
from tests.test_web_coach_dialogue import Forms, login, BASE

setup = base_tests.setup
password_hash = base_tests.password_hash
no_paid_services = base_tests.no_paid_services


class Editor(Forms):
    def __init__(self, html):
        self.area = None
        super().__init__(html)

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == "textarea" and self.current is not None:
            self.area = dict(attrs)["name"]
            self.current["values"][self.area] = ""

    def handle_data(self, data):
        if self.area is not None:
            self.current["values"][self.area] += data

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.area = None
        super().handle_endtag(tag)


def start(client, repo, user, title="阅读方法"):
    repo.create_topic(user.user_id, title)
    row = repo.active_topic(user.user_id)
    path = f"/web/studies/{row['topic_id']}/edit"
    return row, path, Editor(client.get(path).text).values(path)


def test_edit_current_then_continue_uses_corrected_record_without_extra_ai(setup):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    book = materials.add(user.user_id, "book.txt", "先回想再实践。".encode())
    repo.create_topic(user.user_id, "阅读方法", book)
    row = repo.active_topic(user.user_id)
    chunk = materials.chunks(user.user_id, book)[0]
    repo.select_material_part(user.user_id, book, "原书", chunk["chunk_id"])
    row = repo.active_topic(user.user_id)
    before = repo.topic_part(user.user_id)
    path = f"/web/studies/{row['topic_id']}/edit"
    assert path in client.get("/web/welcome").text
    values = Editor(client.get(path).text).values(path)
    changes = {
        "title": "阅读与应用",
        "progress": "讨论了回想。\n还未实践。",
        "next_step": "用一个生活场景举例。",
    }
    result = client.post(path, data={**values, **changes})
    assert result.status_code == 200 and "学习记录已保存" in result.text and calls == []
    assert repo.topic_part(user.user_id) == before
    assert "阅读与应用" in client.get("/web/welcome").text
    assert "还未实践。" in client.get("/web/welcome").text
    base_tests.choose(client, row["topic_id"], "continue")
    assert len(calls) == 1
    assert (
        calls[0][2]["topic"] == "阅读与应用"
        and calls[0][2]["next_step"] == changes["next_step"]
    )
    assert calls[0][3]["sources"][0]["source_id"] == chunk["chunk_id"]
    assert repo.active_topic(user.user_id)["topic_id"] == row["topic_id"]


def test_stale_page_and_duplicate_name_keep_input_and_require_resubmit(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    row, path, values = start(client, repo, user)
    repo.edit_topic(
        user.user_id,
        row["topic_id"],
        "较新名称",
        "新的已讨论内容",
        "新的下一步",
        expected_version=topic_edit_version(row),
    )
    desired = {
        **values,
        "title": "本次名称",
        "progress": "本次进度",
        "next_step": "本次下一步",
    }
    conflict = client.post(path, data=desired)
    assert conflict.status_code == 409 and "较新名称" in conflict.text
    refreshed = Editor(conflict.text).values(path)
    assert {k: refreshed[k] for k in ("title", "progress", "next_step")} == {
        k: desired[k] for k in ("title", "progress", "next_step")
    }
    assert refreshed["version"] != values["version"]
    assert client.post(path, data=refreshed).status_code == 200
    repo.create_topic(user.user_id, "Python 入门")
    fresh = Editor(client.get(path).text).values(path)
    duplicate = client.post(path, data={**fresh, "title": "Ｐｙｔｈｏｎ　入门"})
    assert duplicate.status_code == 409 and "不会合并主题" in duplicate.text
    assert (
        repo.topic(user.user_id, row["topic_id"])["title"] == "本次名称" and calls == []
    )


def test_inactive_edit_and_cancel_do_not_change_current_conversation(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    row, path, values = start(client, repo, user)
    repo.create_topic(user.user_id, "当前沟通主题")
    active = repo.active_topic(user.user_id)
    assert "取消并返回我的学习" in client.get(path).text
    client.get("/web/studies")
    assert repo.topic(user.user_id, row["topic_id"])["title"] == row["title"]
    assert client.post(path, data={**values, "title": "旧主题修正"}).status_code == 200
    assert repo.active_topic(user.user_id) == active and calls == []
    restarted = CoachRepository(repo.database_path)
    assert restarted.topic(user.user_id, row["topic_id"])["title"] == "旧主题修正"


def test_invalid_content_is_preserved_escaped_and_busy_is_explicit(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    row, path, values = start(client, repo, user)
    bad = "<script>ignored</script>\n"
    invalid = client.post(path, data={**values, "title": bad})
    assert (
        invalid.status_code == 400
        and escape(bad, quote=True) in invalid.text
        and "<script>" not in invalid.text
    )
    nonce = secrets.token_urlsafe(32)
    from time import time

    repo.claim(user.user_id, nonce, "尚未结束", now=int(time()))
    pending = client.post(path, data={**values, "title": "想要保留的名称"})
    assert pending.status_code == 409 and "等本轮结束后再保存" in pending.text
    assert Editor(pending.text).values(path)["title"] == "想要保留的名称"
    assert (
        repo.topic(user.user_id, row["topic_id"])["title"] == row["title"]
        and calls == []
    )


@pytest.mark.parametrize(
    "kind",
    ["csrf", "version", "origin", "site", "duplicate", "json", "oversize", "foreign"],
)
def test_edit_protects_forms_and_owner_without_ai(setup, kind):
    app, client, repo, _, user, other, calls = setup
    assert (
        client.get(
            "/web/studies/" + "a" * 32 + "/edit", follow_redirects=False
        ).status_code
        == 303
    )
    login(client)
    row, path, values = start(client, repo, user)
    headers = {}
    if kind == "csrf":
        values["csrf"] = "0" * 64
    if kind == "version":
        values["version"] = "bad"
    if kind == "origin":
        headers["origin"] = "https://evil.example"
    if kind == "site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "oversize":
        values["progress"] = "a" * 25000
    if kind == "foreign":
        with TestClient(app, base_url=BASE) as another:
            login(another, "two@example.com")
            assert another.get(path).status_code == 404
            assert another.post(path, data=values).status_code == 403
        assert calls == []
        return
    if kind == "duplicate":
        result = client.post(
            path,
            content="csrf=x&csrf=y",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    elif kind == "json":
        result = client.post(path, json=values)
    else:
        result = client.post(path, data={**values, "title": "forged"}, headers=headers)
    assert result.status_code == 403 and calls == []
    assert repo.topic(user.user_id, row["topic_id"]) == row


def test_maximum_multibyte_form_and_fixed_database_error_message(setup, monkeypatch):
    _, client, repo, _, user, _, calls = setup
    login(client)
    _, path, values = start(client, repo, user)
    maximum = {"title": "𠮷" * 120, "progress": "𠮷" * 800, "next_step": "𠮷" * 800}
    assert client.post(path, data={**values, **maximum}).status_code == 200
    fresh = Editor(client.get(path).text).values(path)

    def broken(*a, **k):
        raise sqlite3.OperationalError("private source path")

    monkeypatch.setattr(CoachRepository, "edit_topic", broken)
    result = client.post(path, data={**fresh, "title": "下一次修正"})
    assert result.status_code == 503 and "private source path" not in result.text
    assert result.headers["cache-control"] == "no-store" and calls == []


def test_browser_crlf_lines_save_as_newlines_and_stale_invalid_form_still_conflicts(
    setup,
):
    _, client, repo, _, user, _, calls = setup
    login(client)
    row, path, values = start(client, repo, user)
    response = client.post(
        path,
        data={
            **values,
            "progress": "已讨论第一点。\r\n还没有实践。",
            "next_step": "举例。\r再核对。",
        },
    )
    assert response.status_code == 200
    current = repo.topic(user.user_id, row["topic_id"])
    assert current["progress"] == "已讨论第一点。\n还没有实践。"
    assert current["next_step"] == "举例。\n再核对。"
    stale = client.post(path, data={**values, "title": "无效\n旧名称"})
    assert stale.status_code == 409 and "学习记录已在其他页面" in stale.text
    assert "已讨论第一点。" in stale.text
    assert Editor(stale.text).values(path)["title"] == "无效\n旧名称"
    assert repo.topic(user.user_id, row["topic_id"]) == current and calls == []
