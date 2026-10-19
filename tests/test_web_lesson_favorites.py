import sqlite3
from contextlib import closing
from urllib.parse import urlencode, parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api.asset_export import build_export
from conversation.coach_repository import CoachRepository
from tests import test_web_library as base_tests
from tests.test_asset_export import contents
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import login, Forms, BASE, add_user
from tests.test_web_knowledge_search import Links, result_link

setup = base_tests.setup
password_hash = base_tests.password_hash
no_real_services = base_tests.no_real_services


def seed(client, user, directory):
    repo = CoachRepository(directory / "coach_conversations.db")
    identity = saved_lesson(repo, user=user.user_id)
    path = "/web/knowledge/" + identity
    action = "/web/lesson-favorites/" + identity
    html = client.get(path).text
    return repo, identity, path, action, html, Forms(html).values(action)


def test_favorite_find_read_revise_review_unfavorite_and_export_do_not_copy_content(
    setup,
):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, action, html, values = seed(client, user, directory)
    before = repo.knowledge(user.user_id, identity)
    export_before = contents(
        build_export(
            repo.database_path, directory / "coach_library.db", user.user_id, ["saved"]
        )
    )
    assert "收藏为常用教案" in html
    marked = client.post(action, data=values)
    assert marked.status_code == 200 and "已加入常用教案。" in marked.text
    assert "取消常用收藏" in marked.text
    found = client.get("/web/knowledge-favorites?q=最初的例子")
    assert "原版教案" in found.text and "<mark>最初的例子</mark>" in found.text
    link = result_link(found.text, identity)
    assert parse_qs(urlsplit(link).query)["favorites"] == ["1"]
    detail = client.get(link)
    back = next(
        url
        for url in Links(detail.text).links
        if url.startswith("/web/knowledge-favorites?")
    )
    assert parse_qs(urlsplit(back).query)["q"] == ["最初的例子"]
    assert "整理时参考：参考资料 · 片段 1" in detail.text
    assert repo.knowledge(user.user_id, identity) == before
    assert (
        contents(
            build_export(
                repo.database_path,
                directory / "coach_library.db",
                user.user_id,
                ["saved"],
            )
        )
        == export_before
    )
    repo.revise_knowledge(
        user.user_id, identity, 1, title="现在的标题", content="当前重温正文。"
    )
    assert "现在的标题" in client.get("/web/knowledge-favorites?q=重温正文").text
    fresh = client.get(path)
    review = client.post(
        path + "/review", data=Forms(fresh.text).values(path + "/review")
    )
    assert "正在重温教案" in review.text and "现在的标题" in review.text
    assert calls == []
    unmarked = client.post(action, data=Forms(fresh.text).values(action))
    assert (
        unmarked.status_code == 200 and "已取消常用收藏，原教案保留。" in unmarked.text
    )
    assert "还没有收藏教案" in client.get("/web/knowledge-favorites").text
    assert (
        repo.knowledge(user.user_id, identity, saved_only=True)["content"]
        == "当前重温正文。"
    )
    assert client.get(path + "/download").text == "当前重温正文。"
    assert calls == []


def test_old_browser_form_cannot_reapply_after_cancellation_or_cancel_after_refavorite(
    setup,
):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, action, _, old_add = seed(client, user, directory)
    first = client.post(action, data=old_add)
    old_remove = Forms(first.text).values(action)
    assert client.post(action, data=old_add).status_code == 409
    assert client.post(action, data=old_remove).status_code == 200
    stale = client.post(action, data=old_add)
    assert stale.status_code == 409 and "本次没有覆盖" in stale.text
    fresh_add = Forms(client.get(path).text).values(action)
    assert client.post(action, data=fresh_add).status_code == 200
    assert client.post(action, data=old_remove).status_code == 409
    assert (
        repo.lesson_favorite(user.user_id, identity)
        == {"selected": True, "revision": 3}
        and calls == []
    )


@pytest.mark.parametrize(
    "kind",
    [
        "csrf",
        "version",
        "selected",
        "origin",
        "site",
        "json",
        "duplicate",
        "extra",
        "oversize",
        "purpose",
    ],
)
def test_favorite_form_is_session_operation_target_and_desired_state_bound(setup, kind):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, path, action, html, values = seed(client, user, directory)
    kwargs = {"data": values}
    if kind == "csrf":
        kwargs = {"data": {**values, "csrf": "0" * 64}}
    elif kind == "version":
        kwargs = {"data": {**values, "revision": "-1"}}
    elif kind == "selected":
        kwargs = {"data": {**values, "selected": "0"}}
    elif kind == "origin":
        kwargs["headers"] = {"origin": "https://foreign.invalid"}
    elif kind == "site":
        kwargs["headers"] = {"sec-fetch-site": "cross-site"}
    elif kind == "json":
        kwargs = {"json": values}
    elif kind in {"duplicate", "oversize"}:
        kwargs = {
            "content": urlencode(values)
            + ("&selected=1" if kind == "duplicate" else "&x=" + "x" * 512001),
            "headers": {"content-type": "application/x-www-form-urlencoded"},
        }
    elif kind == "extra":
        kwargs = {"data": {**values, "user_id": "other"}}
    elif kind == "purpose":
        kwargs = {
            "data": {**values, "csrf": Forms(html).values(path + "/review")["csrf"]}
        }
    assert client.post(action, **kwargs).status_code == 403
    assert (
        repo.lesson_favorite(user.user_id, identity)
        == {"selected": False, "revision": 0}
        and calls == []
    )


def test_login_ownership_saved_state_and_storage_errors_are_safe(
    setup, password_hash, monkeypatch
):
    app, client, user, calls, directory = setup
    login(client)
    repo, identity, path, action, _, values = seed(client, user, directory)
    with TestClient(app, base_url=BASE) as guest:
        assert (
            guest.get("/web/knowledge-favorites", follow_redirects=False).status_code
            == 303
        )
        assert (
            guest.post(action, data=values, follow_redirects=False).status_code == 303
        )
    add_user(directory, password_hash, "two@example.com", "其他虚构账户")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        assert identity not in other.get("/web/knowledge-favorites").text
        assert other.get(path).status_code == 404
        assert other.post(action, data=values).status_code == 403
    with closing(repo._connect()) as db, db:
        db.execute(
            "UPDATE coach_knowledge SET status='pending' WHERE knowledge_id=?",
            (identity,),
        )
    assert client.post(action, data=values).status_code == 404
    assert action not in client.get(path).text
    with closing(repo._connect()) as db, db:
        db.execute(
            "UPDATE coach_knowledge SET status='saved' WHERE knowledge_id=?",
            (identity,),
        )

    def broken(*a, **k):
        raise sqlite3.OperationalError("private path")

    monkeypatch.setattr(CoachRepository, "set_lesson_favorite", broken)
    failed = client.post(action, data=values)
    assert failed.status_code == 503 and "private path" not in failed.text
    assert failed.headers["cache-control"] == "no-store" and calls == []


def test_favorite_paging_and_search_return_preserve_filter_and_escape_text(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo = CoachRepository(directory / "coach_conversations.db")
    for number in range(22):
        identity = saved_lesson(
            repo,
            user=user.user_id,
            title=f"常用 <script> {number}",
            content="带有独特关键词的正文。",
        )
        repo.set_lesson_favorite(user.user_id, identity, True, 0)
    saved_lesson(
        repo, user=user.user_id, title="未收藏的教案", content="带有独特关键词的正文。"
    )
    first = client.get("/web/knowledge-favorites?q=独特关键词")
    assert first.status_code == 200 and first.text.count('class="library-item"') == 20
    assert "未收藏的教案" not in first.text
    assert "<script>" not in first.text and "&lt;script&gt;" in first.text
    target = next(
        url
        for url in Links(first.text).links
        if url.startswith("?status=") and "page=2" in url
    )
    second = client.get("/web/knowledge-favorites" + target)
    assert second.text.count('class="library-item"') == 2
    link = next(
        url
        for url in Links(second.text).links
        if url.startswith("/web/knowledge/") and "favorites=1" in url
    )
    detail = client.get(link)
    back = next(
        url
        for url in Links(detail.text).links
        if url.startswith("/web/knowledge-favorites?")
    )
    assert parse_qs(urlsplit(back).query)["page"] == ["2"]
    assert "独特关键词" in client.get(back).text
    no_query = client.get("/web/knowledge-favorites?page=2")
    no_query_link = next(
        url
        for url in Links(no_query.text).links
        if url.startswith("/web/knowledge/") and "favorites=1" in url
    )
    assert "返回常用教案" in client.get(no_query_link).text
    for suffix in ["?page=0", "?q=" + "x" * 121]:
        assert client.get("/web/knowledge-favorites" + suffix).status_code == 400
    assert (
        client.get("/web/knowledge/" + identity + "?favorites=bad").status_code == 400
    )
    assert calls == []


def test_favorites_survive_whole_space_backup_and_restore(setup, tmp_path):
    from coach.local_backup import create_backup, restore_backup

    _, client, user, calls, directory = setup
    login(client)
    repo, identity, _, action, _, values = seed(client, user, directory)
    assert client.post(action, data=values).status_code == 200
    (directory / ".coach-mode").write_text("simulated", encoding="ascii")
    archive = create_backup(
        directory, tmp_path.parent / (tmp_path.name + "-favorites.zip")
    )
    restored_path = tmp_path.parent / (tmp_path.name + "-restored")
    restore_backup(archive, restored_path)
    restored = CoachRepository(restored_path / "coach_conversations.db")
    assert restored.lesson_favorite(user.user_id, identity) == {
        "selected": True,
        "revision": 1,
    }
    assert restored.list_knowledge(
        user.user_id, favorites_only=True
    ) == repo.list_knowledge(user.user_id, favorites_only=True)
    assert calls == []
