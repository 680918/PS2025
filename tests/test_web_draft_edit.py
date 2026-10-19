import sqlite3
from html import escape

import pytest
from fastapi.testclient import TestClient

from api.asset_export import build_export, ExportError
from coach.draft_edit import draft_version
from conversation.coach_repository import CoachRepository
from tests import test_web_library as base_tests
from tests.test_web_coach_dialogue import login, Forms, add_user, BASE
from tests.test_web_topic_edit import Editor
from tests.test_lesson_revision import saved_lesson
from tests.test_asset_export import contents

setup = base_tests.setup
password_hash = base_tests.password_hash
no_real_services = base_tests.no_real_services


def seed(client, user, directory):
    repo = CoachRepository(directory / "coach_conversations.db")
    identity = saved_lesson(repo, user=user.user_id, save=False)
    path = "/web/knowledge/" + identity
    page = client.get(path)
    return repo, identity, path, page.text, Editor(page.text).values(path + "/save")


def test_stage_return_reload_search_export_and_explicit_confirmation(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, html, fields = seed(client, user, directory)
    original = repo.knowledge(user.user_id, identity)
    assert f'formaction="{path}/draft"' in html
    changed = {
        "title": "待整理的复习教案",
        "content": "# 学习目标\r\n理解回想。\r\n\r\n```python\r\nif True:\r\n    print(1)\r\n```",
    }
    staged = client.post(path + "/draft", data={**fields, **changed})
    assert staged.status_code == 200 and "草稿已暂存，尚未确认收入知识库" in staged.text
    restarted = CoachRepository(repo.database_path)
    item = restarted.knowledge(user.user_id, identity)
    assert item["status"] == "pending" and item["saved_at"] is None
    assert item["citations"] == original["citations"] and calls == []
    assert restarted.list_knowledge(user.user_id) == []
    assert item["content"] == changed["content"].replace("\r\n", "\n")
    assert "待整理的复习教案" in client.get("/web/knowledge?status=pending&q=回想").text
    assert client.get(path + "/download").status_code == 404
    assert client.get(path + "/edit").status_code == 404
    assert (
        client.post(path + "/review", data={"csrf": fields["csrf"]}).status_code == 403
    )
    payload = b"\n".join(
        contents(
            build_export(
                repo.database_path,
                directory / "coach_library.db",
                user.user_id,
                ["drafts"],
            )
        ).values()
    )
    assert "理解回想。".encode() in payload
    with pytest.raises(ExportError, match="还没有可导出的内容"):
        build_export(
            repo.database_path, directory / "coach_library.db", user.user_id, ["saved"]
        )
    fresh = Editor(client.get(path).text).values(path + "/save")
    confirmed = client.post(path + "/save", data=fresh)
    assert confirmed.status_code == 200 and "已由你确认保存" in confirmed.text
    assert client.get(path + "/download").text == item["content"]
    assert (
        restarted.knowledge_version(user.user_id, identity, 1)["content"]
        == item["content"]
    )


@pytest.mark.parametrize("operation", ["draft", "save", "dismiss"])
def test_old_stage_confirm_and_dismiss_pages_cannot_process_new_content(
    setup, operation
):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, html, fields = seed(client, user, directory)
    before = repo.knowledge(user.user_id, identity)
    repo.change_draft(
        user.user_id,
        identity,
        "stage",
        draft_version(before),
        title="另一页的新草稿",
        content="另一页的新正文。",
    )
    current = repo.knowledge(user.user_id, identity)
    values = (
        Forms(html).values(path + "/dismiss")
        if operation == "dismiss"
        else {**fields, "title": "本次未保存标题", "content": "本次未保存正文。"}
    )
    response = client.post(path + "/" + operation, data=values)
    assert response.status_code == 409 and "草稿已在其他页面更新或处理" in response.text
    if operation != "dismiss":
        assert (
            Editor(response.text).values(path + "/save")["content"]
            == "本次未保存正文。"
        )
    assert repo.knowledge(user.user_id, identity) == current and calls == []


def test_conflict_reconfirmation_saved_race_and_invalid_old_input(setup, monkeypatch):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, _, fields = seed(client, user, directory)
    item = repo.knowledge(user.user_id, identity)
    repo.change_draft(
        user.user_id,
        identity,
        "stage",
        draft_version(item),
        title="新版",
        content="新版正文",
    )
    invalid_old = client.post(
        path + "/draft", data={**fields, "title": "", "content": "保留本次正文"}
    )
    assert invalid_old.status_code == 409
    refreshed = Editor(invalid_old.text).values(path + "/save")
    assert refreshed["content"] == "保留本次正文"
    revised = client.post(path + "/draft", data={**refreshed, "title": "核对后的草稿"})
    assert revised.status_code == 200
    current = Editor(client.get(path).text).values(path + "/save")
    assert client.post(path + "/save", data=current).status_code == 200
    saved = repo.knowledge(user.user_id, identity)
    stale = client.post(
        path + "/draft", data={**current, "content": "旧页面不能改回草稿"}
    )
    assert stale.status_code == 409 and "readonly" in stale.text
    assert "这是待确认草稿。" not in stale.text
    assert "旧页面不能改回草稿" in stale.text and not Forms(stale.text).forms
    assert repo.knowledge(user.user_id, identity) == saved and calls == []

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("private failure")

    monkeypatch.setattr(CoachRepository, "change_draft", broken)
    unavailable = client.post(path + "/draft", data=current)
    assert unavailable.status_code == 503 and not Forms(unavailable.text).forms
    assert "这是待确认草稿。" not in unavailable.text


def test_invalid_values_are_escaped_and_retained_and_error_is_fixed(setup, monkeypatch):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, _, fields = seed(client, user, directory)
    bad = "<script>bad</script>\n"
    response = client.post(
        path + "/draft", data={**fields, "title": bad, "content": "本次填写"}
    )
    assert response.status_code == 400 and escape(bad, quote=True) in response.text
    assert "<script>bad" not in response.text
    assert Editor(response.text).values(path + "/save")["content"] == "本次填写"

    def broken(*a, **k):
        raise sqlite3.OperationalError("private database path")

    monkeypatch.setattr(CoachRepository, "change_draft", broken)
    unavailable = client.post(
        path + "/draft", data={**fields, "content": "错误时保留的正文"}
    )
    assert (
        unavailable.status_code == 503
        and "private database path" not in unavailable.text
    )
    assert (
        "错误时保留的正文" in unavailable.text
        and unavailable.headers["cache-control"] == "no-store"
    )
    assert repo.list_knowledge(user.user_id) == [] and calls == []


@pytest.mark.parametrize(
    "kind",
    [
        "csrf",
        "version",
        "origin",
        "site",
        "json",
        "duplicate",
        "extra",
        "oversize",
        "other-purpose",
    ],
)
def test_draft_writes_protect_form_scope_and_input(setup, kind):
    _, client, user, calls, directory = setup
    assert (
        client.get("/web/knowledge/" + "a" * 32, follow_redirects=False).status_code
        == 303
    )
    login(client)
    repo, identity, path, html, fields = seed(client, user, directory)
    old = repo.knowledge(user.user_id, identity)
    headers = {}
    if kind == "csrf":
        fields["csrf"] = "0" * 64
    if kind == "version":
        fields["version"] = "bad"
    if kind == "origin":
        headers["origin"] = "https://evil.example"
    if kind == "site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "extra":
        fields["user_id"] = "other"
    if kind == "oversize":
        fields["content"] = "x" * 512001
    if kind == "other-purpose":
        fields["csrf"] = Forms(html).values(path + "/dismiss")["csrf"]
    if kind == "json":
        response = client.post(path + "/draft", json=fields)
    elif kind == "duplicate":
        response = client.post(
            path + "/draft",
            content="csrf=x&csrf=y",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    else:
        response = client.post(path + "/draft", data=fields, headers=headers)
    assert response.status_code == 403
    assert repo.knowledge(user.user_id, identity) == old and calls == []


def test_account_isolation_and_maximum_form_and_confirmed_versioning(
    setup, password_hash
):
    app, client, user, calls, directory = setup
    login(client)
    repo, identity, path, _, fields = seed(client, user, directory)
    add_user(directory, password_hash, "two@example.com", "其他账户")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        assert other.get(path).status_code == 404
        assert other.post(path + "/draft", data=fields).status_code == 403
    maximum = {**fields, "title": "𠮷" * 120, "content": "𠮷" * 12000}
    assert client.post(path + "/draft", data=maximum).status_code == 200
    fresh = Editor(client.get(path).text).values(path + "/save")
    assert client.post(path + "/save", data=fresh).status_code == 200
    assert (
        repo.revise_knowledge(
            user.user_id, identity, 1, title="保存后修订", content="修订正文"
        )
        == "updated"
    )
    assert repo.knowledge_version(user.user_id, identity, 1)["content"] == "𠮷" * 12000
    assert repo.knowledge(user.user_id, identity)["revision"] == 2 and calls == []
