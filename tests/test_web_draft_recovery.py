import sqlite3
from contextlib import closing
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from api.asset_export import build_export, ExportError
from conversation.coach_repository import CoachRepository
from tests import test_web_library as base_tests
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import login, Forms, BASE, add_user
from tests.test_web_topic_edit import Editor

setup = base_tests.setup
password_hash = base_tests.password_hash
no_real_services = base_tests.no_real_services


def seed(client, user, directory):
    repo = CoachRepository(directory / "coach_conversations.db")
    identity = saved_lesson(repo, user=user.user_id, save=False)
    path = "/web/knowledge/" + identity
    old_html = client.get(path).text
    response = client.post(
        path + "/dismiss", data=Forms(old_html).values(path + "/dismiss")
    )
    assert response.status_code == 200 and "草稿已移出" in response.text
    removed_path = "/web/knowledge-removed/" + identity
    html = client.get(removed_path).text
    return (
        repo,
        identity,
        path,
        removed_path,
        old_html,
        Forms(html).values(removed_path + "/restore"),
    )


def test_removed_list_preview_restore_edit_and_confirm_without_ai(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, removed_path, _, values = seed(client, user, directory)
    item = repo.knowledge(user.user_id, identity, include_dismissed=True)
    listing = client.get("/web/knowledge-removed?q=最初的例子")
    assert removed_path in listing.text and "<mark>最初的例子</mark>" in listing.text
    assert identity not in client.get("/web/knowledge?status=pending").text
    assert client.get(path).status_code == 404
    preview = client.get(removed_path)
    assert "参考资料 · 片段 1" in preview.text and "原始依据" in preview.text
    assert "<h1>原文</h1>" in preview.text
    assert "恢复到草稿目录" in preview.text and "确认保存到知识库" not in preview.text
    assert preview.headers["cache-control"] == "no-store"
    assert client.get(path + "/download").status_code == 404
    with pytest.raises(ExportError):
        build_export(
            repo.database_path, directory / "coach_library.db", user.user_id, ["drafts"]
        )
    response = client.post(removed_path + "/restore", data=values)
    assert (
        response.status_code == 200
        and "已恢复到草稿目录，尚未确认保存到知识库" in response.text
    )
    current = repo.knowledge(user.user_id, identity)
    assert (
        current["content"] == item["content"]
        and current["citations"] == item["citations"]
    )
    assert current["status"] == "pending" and current["saved_at"] is None
    assert calls == [] and repo.list_knowledge(user.user_id) == []
    assert identity not in client.get("/web/knowledge-removed").text
    assert client.get(removed_path, follow_redirects=False).headers["location"] == path
    repeat = client.post(removed_path + "/restore", data=values)
    assert repeat.status_code == 409 and "没有重复恢复" in repeat.text
    fresh = Editor(client.get(path).text).values(path + "/save")
    assert (
        client.post(
            path + "/draft", data={**fresh, "title": "找回后的草稿"}
        ).status_code
        == 200
    )
    fresh = Editor(client.get(path).text).values(path + "/save")
    assert client.post(path + "/save", data=fresh).status_code == 200
    assert client.post(removed_path + "/restore", data=values).status_code == 409
    assert (
        repo.knowledge(user.user_id, identity, saved_only=True)["title"]
        == "找回后的草稿"
    )
    assert calls == []


@pytest.mark.parametrize("operation", ["draft", "save", "dismiss"])
def test_old_browser_forms_remain_invalid_after_restoring_same_text(setup, operation):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, removed_path, old_html, values = seed(client, user, directory)
    assert client.post(removed_path + "/restore", data=values).status_code == 200
    current = repo.knowledge(user.user_id, identity)
    old = (
        Forms(old_html).values(path + "/dismiss")
        if operation == "dismiss"
        else Editor(old_html).values(path + "/save")
    )
    result = client.post(path + "/" + operation, data=old)
    assert result.status_code == 409
    assert repo.knowledge(user.user_id, identity) == current and calls == []


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
        "large",
        "purpose",
    ],
)
def test_restore_rejects_invalid_submissions(setup, kind):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, removed_path, old_html, values = seed(client, user, directory)
    kwargs = {"data": values}
    if kind in {"csrf", "version"}:
        kwargs = {"data": {**values, kind: "a" * 64}}
    elif kind == "origin":
        kwargs["headers"] = {"origin": "https://foreign.invalid"}
    elif kind == "site":
        kwargs["headers"] = {"sec-fetch-site": "cross-site"}
    elif kind == "json":
        kwargs = {"json": values}
    elif kind in {"duplicate", "large"}:
        kwargs = {
            "content": urlencode(values)
            + (
                "&version=" + values["version"]
                if kind == "duplicate"
                else "&x=" + "x" * 512001
            ),
            "headers": {"content-type": "application/x-www-form-urlencoded"},
        }
    elif kind == "extra":
        kwargs = {"data": {**values, "title": "不能顺带修改"}}
    elif kind == "purpose":
        kwargs = {"data": Forms(old_html).values(path + "/dismiss")}
    before = repo.knowledge(user.user_id, identity, include_dismissed=True)
    result = client.post(removed_path + "/restore", **kwargs)
    assert result.status_code == 403
    assert repo.knowledge(user.user_id, identity, include_dismissed=True) == before
    assert calls == []


def test_removed_pages_are_private_and_cross_account_restore_is_denied(
    setup, password_hash
):
    app, client, user, calls, directory = setup
    login(client)
    repo, identity, path, removed_path, _, values = seed(client, user, directory)
    with TestClient(app, base_url=BASE) as guest:
        for target in ("/web/knowledge-removed", removed_path):
            assert guest.get(target, follow_redirects=False).status_code == 303
        assert (
            guest.post(
                removed_path + "/restore", data=values, follow_redirects=False
            ).status_code
            == 303
        )
    add_user(directory, password_hash, "other@example.com", "另一位虚构用户")
    with TestClient(app, base_url=BASE) as other:
        login(other, "other@example.com")
        assert identity not in other.get("/web/knowledge-removed").text
        assert other.get(removed_path).status_code == 404
        assert other.post(removed_path + "/restore", data=values).status_code == 403
    assert (
        repo.knowledge(user.user_id, identity, include_dismissed=True)["status"]
        == "dismissed"
    )


def test_removed_search_paging_escaping_and_fixed_storage_errors(setup, monkeypatch):
    _, client, user, calls, directory = setup
    login(client)
    repo = CoachRepository(directory / "coach_conversations.db")
    identities = []
    for number in range(22):
        identity = saved_lesson(
            repo,
            user=user.user_id,
            title=f"移出 <script> {number}",
            content="正文 稀有关键词 <script>alert(1)</script>",
            save=False,
        )
        repo.confirm_knowledge(user.user_id, identity, save=False)
        identities.append(identity)
    first = client.get("/web/knowledge-removed?q=稀有关键词")
    assert first.status_code == 200 and "<mark>稀有关键词</mark>" in first.text
    assert first.text.count('class="library-item"') == 20
    assert "q=%E7%A8%80%E6%9C%89%E5%85%B3%E9%94%AE%E8%AF%8D&amp;page=2" in first.text
    assert (
        client.get("/web/knowledge-removed?q=稀有关键词&page=2").text.count(
            'class="library-item"'
        )
        == 2
    )
    assert "<script>" not in first.text and "&lt;script&gt;" in first.text
    last = client.get("/web/knowledge-removed?q=稀有关键词&page=2")
    from html.parser import HTMLParser

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and attrs.get("href", "").startswith(
                "/web/knowledge-removed/"
            ):
                self.path = attrs["href"]

    links = Links()
    links.feed(last.text)
    detail = client.get(links.path)
    assert (
        "/web/knowledge-removed?q=%E7%A8%80%E6%9C%89%E5%85%B3%E9%94%AE%E8%AF%8D&amp;page=2"
        in detail.text
    )
    assert client.get(links.path + "&page=0").status_code == 400
    assert (
        client.get(
            "/web/knowledge-removed/" + identities[0] + "?q=" + "x" * 121
        ).status_code
        == 400
    )
    for suffix in ("?page=0", "?q=" + "x" * 121):
        assert client.get("/web/knowledge-removed" + suffix).status_code == 400
    preview_path = "/web/knowledge-removed/" + identities[0]
    values = Forms(client.get(preview_path).text).values(preview_path + "/restore")

    def broken(*a, **k):
        raise sqlite3.OperationalError("private database info")

    monkeypatch.setattr(CoachRepository, "restore_draft", broken)
    failed = client.post(preview_path + "/restore", data=values)
    assert failed.status_code == 503 and "private database info" not in failed.text
    assert (
        repo.knowledge(user.user_id, identities[0], include_dismissed=True)["status"]
        == "dismissed"
    )
    assert calls == []


def test_unit_link_and_generation_are_preserved_by_whole_space_backup(setup, tmp_path):
    from coach.local_backup import create_backup, restore_backup

    _, client, user, _, directory = setup
    login(client)
    repo, identity, _, removed_path, _, values = seed(client, user, directory)
    with closing(repo._connect()) as db, db:
        db.execute(
            "INSERT INTO coach_knowledge_units VALUES(?,?,?,?,?)",
            (
                identity,
                user.user_id,
                "book",
                "unit",
                '{"material_id":"book","unit_id":"unit","material_title":"虚构书籍","unit_title":"本单元","range":"片段 1","explained":1,"total":1,"batch":1,"batch_count":1,"sources":[{"locator":"片段 1"}]}',
            ),
        )
    before = repo.knowledge(user.user_id, identity, include_dismissed=True)[
        "unit_summary"
    ]
    assert "学习单元：本单元" in client.get(removed_path).text
    assert (
        client.post(
            removed_path + "/restore", data=values, follow_redirects=False
        ).status_code
        == 303
    )
    (directory / ".coach-mode").write_text("simulated", encoding="ascii")
    archive = create_backup(
        directory, tmp_path.parent / (tmp_path.name + "-recovery.zip")
    )
    target = tmp_path.parent / (tmp_path.name + "-restored")
    restore_backup(archive, target)
    restored = CoachRepository(target / "coach_conversations.db")
    item = restored.knowledge(user.user_id, identity)
    assert item["unit_summary"] == before and item["draft_generation"] == 1
    assert item["status"] == "pending"
