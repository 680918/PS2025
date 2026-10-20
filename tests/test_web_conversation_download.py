import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from api.conversation_export import conversation_document
from tests import test_web_conversation_review as base
from tests.test_conversation_review import topic, turn
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_paid_services = base.no_paid_services
no_plain_smtp = base.no_plain_smtp


def path(identity):
    return f"/web/conversations/{identity}/download"


def test_detail_download_is_exactly_one_owned_record_without_state_changes(setup):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    a = topic(repo, "原主题", user=user.user_id)
    identity = turn(
        repo,
        "完整问题\n下一行",
        '## 原来的回答\n\n```python\nif ok:\n    print("原样")\n```',
        user=user.user_id,
        citations=[
            {"title": "当时书名", "locator": "第2页", "excerpt": "这是引用快照"}
        ],
    )
    topic(repo, "当前主题", user=user.user_id, now=110)
    turn(repo, "OTHER_TURN_CONTENT", user=user.user_id, now=120)
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_topics SET title=? WHERE user_id=? AND topic_id=?",
            ("下载时的新主题名", user.user_id, a),
        )
    before = {p: p.read_bytes() for p in [repo.database_path, materials.database_path]}
    detail = client.get(
        f"/web/conversations/{identity}", params={"q": "完整", "topic": a, "page": 2}
    )
    assert path(identity) in Links(detail.text).links
    result = client.get(path(identity))
    assert result.status_code == 200
    assert (
        result.content
        == conversation_document(repo.conversation_record(user.user_id, identity))[0]
    )
    text = result.content.decode()
    assert "下载时的新主题名" in text and "这是引用快照" in text
    assert "OTHER_TURN_CONTENT" not in text
    assert "frame-ancestors" in result.headers["content-security-policy"]
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert result.headers["referrer-policy"] == "no-referrer"
    assert result.headers["content-type"] == "application/octet-stream"
    assert int(result.headers["content-length"]) == len(result.content)
    disposition = result.headers["content-disposition"]
    assert disposition.startswith(
        f'attachment; filename="zhixing-dialogue-{identity}.html";'
    )
    assert "知行-问答-" in unquote(disposition) and "新主题名" not in unquote(
        disposition
    )
    assert all(p.read_bytes() == b for p, b in before.items()) and calls == []


@pytest.mark.parametrize("state", ["pending", "failed"])
def test_pending_and_failed_export_does_not_expire_or_resend(setup, state):
    _, client, repo, _, user, _, calls = setup
    login(client)
    identity = turn(repo, "保存问题", user=user.user_id, status=state, now=10)
    before = repo.database_path.read_bytes()
    result = client.get(path(identity))
    assert result.status_code == 200 and "保存问题" in result.content.decode()
    assert (
        "尚未完成" if state == "pending" else "未取得回复"
    ) in result.content.decode()
    assert repo.database_path.read_bytes() == before and calls == []


def test_guest_other_account_and_missing_turn_cannot_download(setup):
    app, client, repo, _, user, _, calls = setup
    login(client)
    identity = turn(repo, "OWN_PRIVATE_QUESTION", user=user.user_id)
    with TestClient(app, base_url=BASE) as stranger:
        response = stranger.get(path(identity), follow_redirects=False)
        assert (
            response.status_code == 303 and response.headers["location"] == "/web/login"
        )
        login(stranger, "two@example.com")
        for number in [identity, identity + 999]:
            response = stranger.get(path(number))
            assert response.status_code == 404
            assert "OWN_PRIVATE_QUESTION" not in response.text
            assert "content-disposition" not in response.headers
    assert calls == []


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://outside.example"},
        {"sec-fetch-site": "cross-site"},
        {"origin": "null"},
    ],
)
def test_cross_site_requests_are_rejected(setup, headers):
    _, client, repo, _, user, _, calls = setup
    login(client)
    identity = turn(repo, "问题", user=user.user_id)
    assert client.get(path(identity), headers=headers).status_code == 403
    assert calls == []


@pytest.mark.parametrize("suffix", ["?user_id=other", "?format=html", "?q=x&q=y"])
def test_extra_parameters_do_not_override_export_scope(setup, suffix):
    _, client, repo, _, user, _, _ = setup
    login(client)
    identity = turn(repo, "问题", user=user.user_id)
    response = client.get(path(identity) + suffix)
    assert response.status_code == 400 and "content-disposition" not in response.headers


@pytest.mark.parametrize("identity", ["0", "-1", "01", "abc", "9223372036854775808"])
def test_invalid_identifiers_are_rejected(setup, identity):
    _, client, _, _, _, _, _ = setup
    login(client)
    assert client.get(path(identity)).status_code == 404


def test_database_and_render_failures_release_preparation_slots(setup, monkeypatch):
    _, client, repo, _, user, _, _ = setup
    login(client)
    identity = turn(repo, "问题", user=user.user_id)
    original = type(repo).conversation_record

    def broken(*a):
        raise sqlite3.OperationalError("SECRET_DATABASE_PATH")

    monkeypatch.setattr(type(repo), "conversation_record", broken)
    for _ in range(2):
        response = client.get(path(identity))
        assert (
            response.status_code == 503 and "SECRET_DATABASE_PATH" not in response.text
        )
    monkeypatch.setattr(
        type(repo),
        "conversation_record",
        lambda *a: {**original(*a), "citations": None},
    )
    assert client.get(path(identity)).status_code == 503
    monkeypatch.setattr(type(repo), "conversation_record", original)
    assert client.get(path(identity)).status_code == 200


def test_download_limit_is_independent_of_reading_and_ai(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    identity = turn(repo, "问题", user=user.user_id)
    before = repo.database_path.read_bytes()
    assert all(client.get(path(identity)).status_code == 200 for _ in range(6))
    rejected = client.get(path(identity))
    assert rejected.status_code == 429 and int(rejected.headers["retry-after"]) > 0
    assert client.get(f"/web/conversations/{identity}").status_code == 200
    assert repo.database_path.read_bytes() == before and calls == []


def test_two_concurrent_preparations_reject_third_then_recover(setup, monkeypatch):
    _, client, repo, _, user, _, _ = setup
    login(client)
    identity = turn(repo, "问题", user=user.user_id)
    original = type(repo).conversation_record
    started = Barrier(3)
    release = Event()

    def held(*a):
        started.wait(timeout=10)
        assert release.wait(timeout=10)
        return original(*a)

    monkeypatch.setattr(type(repo), "conversation_record", held)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.get, path(identity)) for _ in range(2)]
        try:
            started.wait(timeout=10)
            assert client.get(path(identity)).status_code == 503
        finally:
            release.set()
        assert [future.result().status_code for future in futures] == [200, 200]
    monkeypatch.setattr(type(repo), "conversation_record", original)
    assert client.get(path(identity)).status_code == 200
