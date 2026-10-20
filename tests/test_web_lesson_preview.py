import secrets
import sqlite3
from html import escape

import pytest
from fastapi.testclient import TestClient

from coach.draft_edit import draft_version
from tests import test_web_lesson_revision as base
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_topic_edit import Editor

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services

CONTENT = "## 预览知识点\n\n| 方法 | 用途 |\n| --- | --- |\n| 回想 | 巩固 |\n\n~~~python\nif ready:\n    practice()\n~~~\n\n<script>只作文字</script>"


def editor(setup, kind):
    _, client, repo, user, identity = setup
    if kind == "draft":
        identity = saved_lesson(repo, user.user_id, title="待确认的草稿", save=False)
    action = f"/web/knowledge/{identity}/" + ("save" if kind == "draft" else "revise")
    page = client.get(
        f"/web/knowledge/{identity}" + ("" if kind == "draft" else "/edit")
    )
    fields = Editor(page.text).values(action)
    return identity, action, f"/web/lesson-preview/{identity}/{kind}", fields


def other_edit(repo, user, identity, kind):
    current = repo.knowledge(user, identity)
    if kind == "draft":
        assert (
            repo.change_draft(
                user,
                identity,
                "stage",
                draft_version(current),
                title="另一页草稿",
                content="另一页已修改",
            )
            == "staged"
        )
    else:
        assert (
            repo.revise_knowledge(
                user,
                identity,
                current["revision"],
                title="另一页新版",
                content="另一页已修改",
            )
            == "updated"
        )


@pytest.mark.parametrize("kind", ["draft", "saved"])
def test_preview_keeps_inputs_and_database_unchanged_until_explicit_save(setup, kind):
    _, client, repo, user, _ = setup
    identity, action, preview, fields = editor(setup, kind)
    values = {**fields, "title": "  本次填写的标题  ", "content": CONTENT}
    before = repo.database_path.read_bytes()
    response = client.post(preview, data=values)
    assert response.status_code == 200
    assert 'id="lesson-edit-preview"' in response.text
    assert "本次填写尚未保存" in response.text
    assert "<table>" in response.text and "<pre " in response.text
    assert "    practice()" in response.text
    assert "&lt;script&gt;只作文字&lt;/script&gt;" in response.text
    assert "<script>只作文字</script>" not in response.text
    assert (
        'href="#lesson-title"' in response.text
        if kind == "draft"
        else 'href="#revision-title"' in response.text
    )
    returned = Editor(response.text).values(action)
    assert returned == values
    assert repo.database_path.read_bytes() == before
    assert "script-src" not in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    saved = client.post(action, data=returned)
    assert saved.status_code == 200
    item = repo.knowledge(user.user_id, identity)
    assert item["status"] == "saved" and item["title"] == "本次填写的标题"
    assert item["content"] == CONTENT
    assert item["revision"] == (1 if kind == "draft" else 2)
    with sqlite3.connect(repo.database_path) as db:
        assert db.execute("SELECT count(*) FROM coach_ai_usage").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["draft", "saved"])
def test_old_form_is_not_silently_rebased_by_preview(setup, kind):
    _, client, repo, user, _ = setup
    identity, action, preview, fields = editor(setup, kind)
    values = {**fields, "title": "我的未保存标题", "content": "我的未保存正文"}
    other_edit(repo, user.user_id, identity, kind)
    before = repo.database_path.read_bytes()
    response = client.post(preview, data=values)
    assert response.status_code == 409 and "另一页面已更新或处理" in response.text
    assert 'id="lesson-edit-preview"' not in response.text
    assert "我的未保存正文" in response.text
    assert Editor(response.text).values(action)["content"] == values["content"]
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize("kind", ["draft", "saved"])
def test_changes_after_preview_still_trigger_original_save_conflict(setup, kind):
    _, client, repo, user, _ = setup
    identity, action, preview, fields = editor(setup, kind)
    response = client.post(
        preview, data={**fields, "title": "我的内容", "content": "尚未保存的修改"}
    )
    assert response.status_code == 200
    returned = Editor(response.text).values(action)
    other_edit(repo, user.user_id, identity, kind)
    before = repo.database_path.read_bytes()
    rejected = client.post(action, data=returned)
    assert rejected.status_code == 409 and "尚未保存的修改" in rejected.text
    assert repo.knowledge(user.user_id, identity)["content"] == "另一页已修改"
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize("operation", ["save", "dismiss"])
def test_processed_draft_keeps_read_only_copy_and_is_not_restored(setup, operation):
    _, client, repo, user, _ = setup
    identity, _, preview, fields = editor(setup, "draft")
    current = repo.knowledge(user.user_id, identity)
    assert repo.change_draft(
        user.user_id,
        identity,
        operation,
        draft_version(current),
        title="另一页确认",
        content="另一页确认正文",
    ) == ("saved_now" if operation == "save" else "dismissed")
    before = repo.database_path.read_bytes()
    response = client.post(
        preview, data={**fields, "title": "尚未保留的标题", "content": "尚未保留的正文"}
    )
    assert response.status_code == (409 if operation == "save" else 404)
    assert (
        'id="draft-copy-content" readonly'
        if operation == "save"
        else 'id="preview-copy-content" readonly'
    ) in response.text
    assert "尚未保留的正文" in response.text
    assert f'action="/web/knowledge/{identity}/save"' not in response.text
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize(
    "title,content",
    [
        ("", CONTENT),
        ("字" * 121, CONTENT),
        ("标题\n换行", CONTENT),
        ("标题", ""),
        ("标题", "字" * 12001),
        ("标题", "内容\x00"),
    ],
    ids=[
        "empty-title",
        "long-title",
        "newline-title",
        "empty-body",
        "long-body",
        "control-character",
    ],
)
def test_invalid_content_preserves_input_without_writes(setup, title, content):
    _, client, repo, _, _ = setup
    _, action, preview, fields = editor(setup, "saved")
    before = repo.database_path.read_bytes()
    response = client.post(preview, data={**fields, "title": title, "content": content})
    assert (
        response.status_code == 400 and 'id="lesson-edit-preview"' not in response.text
    )
    assert Editor(response.text).values(action)["content"] == content
    assert repo.database_path.read_bytes() == before


def test_maximum_four_byte_unicode_preview_fits_body_limit_without_saving(setup):
    _, client, repo, _, _ = setup
    _, action, preview, fields = editor(setup, "saved")
    values = {**fields, "title": "😀" * 120, "content": "😀" * 12000}
    before = repo.database_path.read_bytes()
    response = client.post(preview, data=values)
    assert response.status_code == 200
    assert Editor(response.text).values(action) == values
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize(
    "kind", ["csrf", "extra", "duplicate", "json", "origin", "opaque", "oversize"]
)
def test_forged_or_malformed_preview_is_rejected_without_state_changes(setup, kind):
    _, client, repo, _, _ = setup
    _, _, preview, fields = editor(setup, "saved")
    before = repo.database_path.read_bytes()
    headers = {}
    if kind == "csrf":
        fields["csrf"] = "a" * 64
    if kind == "extra":
        fields["user_id"] = "someone-else"
    if kind == "origin":
        headers["origin"] = "https://outside.example"
    if kind == "opaque":
        headers["origin"] = "null"
    if kind == "oversize":
        fields["content"] = "x" * 200001
    if kind == "json":
        response = client.post(preview, json=fields)
    elif kind == "duplicate":
        response = client.post(
            preview,
            content="csrf=x&csrf=y&revision=1&title=x&content=y",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    else:
        response = client.post(preview, data=fields, headers=headers)
    assert response.status_code == 403
    assert repo.database_path.read_bytes() == before


def test_guests_other_accounts_and_invalid_modes_cannot_preview_owned_content(setup):
    app, client, _, _, _ = setup
    identity, _, preview, fields = editor(setup, "saved")
    with TestClient(app, base_url=BASE) as stranger:
        assert (
            stranger.post(preview, data=fields, follow_redirects=False).status_code
            == 303
        )
        login(stranger, "two@example.com")
        assert stranger.post(preview, data=fields).status_code == 403
    assert (
        client.post(f"/web/lesson-preview/{identity}/anything", data=fields).status_code
        == 404
    )
    assert client.post(preview + "?user_id=x", data=fields).status_code == 400


def test_preview_while_reply_is_pending_does_not_expire_it_or_consume_new_usage(setup):
    _, client, repo, user, _ = setup
    _, _, preview, fields = editor(setup, "saved")
    nonce = secrets.token_urlsafe(32)
    assert (
        repo.claim(user.user_id, nonce, "未结束的提问", now=1, ai_kind="dialogue")
        == "claimed"
    )
    before = repo.database_path.read_bytes()
    response = client.post(
        preview,
        data=fields,
        headers={"origin": "null", "sec-fetch-site": "same-origin"},
    )
    assert response.status_code == 200
    assert repo.database_path.read_bytes() == before
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT status FROM coach_turns WHERE nonce=?", (nonce,)
            ).fetchone()[0]
            == "pending"
        )
        assert db.execute("SELECT count(*) FROM coach_ai_usage").fetchone()[0] == 1


def test_preview_limit_preserves_copy_and_does_not_disable_original_save(setup):
    _, client, repo, _, _ = setup
    _, action, preview, fields = editor(setup, "saved")
    values = {**fields, "title": "暂未保存的标题", "content": "待保留的正文<script>"}
    before = repo.database_path.read_bytes()
    assert all(client.post(preview, data=values).status_code == 200 for _ in range(12))
    response = client.post(preview, data=values)
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
    assert 'id="preview-copy-content" readonly' in response.text
    assert escape(values["content"]) in response.text
    assert repo.database_path.read_bytes() == before
    assert client.post(action, data=values).status_code == 200


def test_database_failure_keeps_safe_copy_and_does_not_expose_internal_details(
    setup, monkeypatch
):
    _, client, repo, _, _ = setup
    _, _, preview, fields = editor(setup, "saved")
    original = type(repo).knowledge

    def broken(*a, **k):
        raise sqlite3.OperationalError("SECRET_INTERNAL_PATH")

    monkeypatch.setattr(type(repo), "knowledge", broken)
    response = client.post(
        preview, data={**fields, "title": "我的填写", "content": "正文<script>"}
    )
    assert response.status_code == 503 and "SECRET_INTERNAL_PATH" not in response.text
    assert (
        'id="preview-copy-content" readonly' in response.text
        and "正文&lt;script&gt;" in response.text
    )
    monkeypatch.setattr(type(repo), "knowledge", original)
    assert client.post(preview, data=fields).status_code == 200
