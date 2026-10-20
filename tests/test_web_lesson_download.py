import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from api.lesson_export import lesson_document
from tests import test_web_lesson_revision as base
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def path(identity):
    return f"/web/knowledge/{identity}/readable"


def test_saved_lesson_download_keeps_latest_version_sources_and_markdown_without_writes(
    setup,
):
    _, client, repo, user, identity = setup
    assert (
        repo.revise_knowledge(
            user.user_id,
            identity,
            1,
            title="下载时的新版标题",
            content="## 新版知识点\n\n~~~python\nif ready:\n    practice()\n~~~",
            now=2000,
        )
        == "updated"
    )
    item = repo.knowledge(user.user_id, identity)
    before = repo.database_path.read_bytes()
    page = client.get(f"/web/knowledge/{identity}")
    assert path(identity) in Links(page.text).links
    assert "下载阅读版" in page.text and "下载 Markdown" in page.text
    response = client.get(path(identity))
    assert response.status_code == 200
    assert response.content == lesson_document(item)[0]
    text = response.content.decode()
    assert "下载时的新版标题" in text and "第 2 版" in text and "原始依据" in text
    assert "原版教案" not in text
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors" in response.headers["content-security-policy"]
    assert int(response.headers["content-length"]) == len(response.content)
    assert response.headers["content-disposition"].startswith(
        f'attachment; filename="zhixing-lesson-{identity}.html";'
    )
    assert "知行-教案-" in unquote(response.headers["content-disposition"])
    assert "新版标题" not in unquote(response.headers["content-disposition"])
    markdown = client.get(f"/web/knowledge/{identity}/download")
    assert markdown.status_code == 200 and markdown.text == item["content"]
    assert "text/markdown" in markdown.headers["content-type"]
    assert repo.database_path.read_bytes() == before
    assert (
        repo.revise_knowledge(
            user.user_id, identity, 2, title="后来的版本", content="后来内容", now=2001
        )
        == "updated"
    )
    newest = client.get(path(identity))
    assert (
        "第 3 版" in newest.content.decode() and "后来的版本" in newest.content.decode()
    )
    assert "后来的版本" not in text


def test_visitors_other_accounts_missing_drafts_and_dismissed_are_not_downloadable(
    setup,
):
    app, client, repo, user, identity = setup
    with TestClient(app, base_url=BASE) as stranger:
        assert stranger.get(path(identity), follow_redirects=False).status_code == 303
        login(stranger, "two@example.com")
        assert stranger.get(path(identity)).status_code == 404
    draft = saved_lesson(repo, user.user_id, title="尚未确认", save=False)
    assert path(draft) not in Links(client.get(f"/web/knowledge/{draft}").text).links
    assert client.get(path(draft)).status_code == 404
    repo.confirm_knowledge(user.user_id, draft, save=False)
    assert client.get(path(draft)).status_code == 404
    assert client.get(path("b" * 32)).status_code == 404
    assert client.get(path("not-a-lesson")).status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://outside.example"},
        {"origin": "null"},
        {"sec-fetch-site": "cross-site"},
        {"origin": "null", "sec-fetch-site": "cross-site"},
    ],
)
def test_cross_site_requests_are_rejected_without_content(setup, headers):
    _, client, repo, _, identity = setup
    before = repo.database_path.read_bytes()
    response = client.get(path(identity), headers=headers)
    assert response.status_code == 403 and "原始依据" not in response.text
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize("query", ["user_id=one", "format=html", "q=x&q=y"])
def test_extra_query_fields_are_rejected(setup, query):
    _, client, _, _, identity = setup
    assert client.get(path(identity) + "?" + query).status_code == 400


def test_opaque_same_origin_request_and_pending_message_are_read_only(setup):
    _, client, repo, user, identity = setup
    assert (
        repo.claim(
            user.user_id, secrets.token_urlsafe(32), "待回复", now=1, ai_kind="dialogue"
        )
        == "claimed"
    )
    before = repo.database_path.read_bytes()
    response = client.get(
        path(identity), headers={"origin": "null", "sec-fetch-site": "same-origin"}
    )
    assert response.status_code == 200
    assert repo.database_path.read_bytes() == before
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM coach_turns WHERE status='pending'"
            ).fetchone()[0]
            == 1
        )
        assert db.execute("SELECT count(*) FROM coach_ai_usage").fetchone()[0] == 1


def test_errors_do_not_expose_details_or_keep_export_slots(setup, monkeypatch):
    _, client, repo, _, identity = setup
    original = type(repo).knowledge

    def broken(*a, **k):
        raise sqlite3.OperationalError("SECRET_DATABASE_LOCATION")

    monkeypatch.setattr(type(repo), "knowledge", broken)
    for _ in range(2):
        response = client.get(path(identity))
        assert (
            response.status_code == 503
            and "SECRET_DATABASE_LOCATION" not in response.text
        )
    monkeypatch.setattr(
        type(repo),
        "knowledge",
        lambda *a, **k: {**original(*a, **k), "citations": None},
    )
    assert client.get(path(identity)).status_code == 503
    monkeypatch.setattr(type(repo), "knowledge", original)
    assert client.get(path(identity)).status_code == 200


def test_readable_limit_does_not_disable_reading_or_markdown_download(setup):
    _, client, repo, _, identity = setup
    before = repo.database_path.read_bytes()
    assert all(client.get(path(identity)).status_code == 200 for _ in range(6))
    response = client.get(path(identity))
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
    assert client.get(f"/web/knowledge/{identity}").status_code == 200
    assert client.get(f"/web/knowledge/{identity}/download").status_code == 200
    assert repo.database_path.read_bytes() == before


def test_two_parallel_preparations_reject_third_and_release_slots(setup, monkeypatch):
    _, client, repo, _, identity = setup
    original = type(repo).knowledge
    started, release = Barrier(3), Event()

    def held(*a, **k):
        started.wait(timeout=10)
        assert release.wait(timeout=10)
        return original(*a, **k)

    monkeypatch.setattr(type(repo), "knowledge", held)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(client.get, path(identity)) for _ in range(2)]
        try:
            started.wait(timeout=10)
            assert client.get(path(identity)).status_code == 503
        finally:
            release.set()
        assert [job.result().status_code for job in jobs] == [200, 200]
    monkeypatch.setattr(type(repo), "knowledge", original)
    assert client.get(path(identity)).status_code == 200
