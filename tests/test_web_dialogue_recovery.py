import secrets
import sqlite3
from time import time

import pytest
from fastapi.testclient import TestClient

from api import account_pages
from api.account_app import create_account_app
from coach.dialogue import send_dialogue, CoachAnswer
from conversation.coach_repository import CoachRepository, PENDING_LIFETIME
from tests import test_web_coach_dialogue as base
from tests.test_web_coach_dialogue import login, form, add_user, BASE

password_hash = base.password_hash
no_real_services = base.no_external_services


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "恢复体验者")
    calls = []

    def respond(*args, **kwargs):
        calls.append(args)
        return CoachAnswer("这是虚构回复。", None, [])

    app = create_account_app(tmp_path, dialogue_responder=respond)
    with TestClient(app, base_url=BASE) as client:
        yield app, client, user, calls, tmp_path


def test_owned_status_is_private_read_only_and_stale_pending_does_not_expire_on_check(
    setup,
):
    _, client, user, calls, directory = setup
    login(client)
    repo = CoachRepository(directory / "coach_conversations.db")
    nonce = secrets.token_urlsafe(32)
    repo.claim(
        user.user_id,
        nonce,
        "私人正文不出现在状态响应",
        now=int(time()),
        ai_kind="dialogue",
    )
    before = repo.database_path.read_bytes()
    snapshot_time = int(time())
    usage = repo.ai_usage(user.user_id, now=snapshot_time)
    pending = client.get("/web/coach/status", params={"nonce": nonce})
    assert pending.status_code == 200 and pending.json() == {"status": "pending"}
    assert (
        pending.headers["cache-control"] == "no-store"
        and pending.headers["referrer-policy"] == "no-referrer"
    )
    assert "私人正文" not in pending.text
    assert client.get(
        "/web/coach/status", params={"nonce": secrets.token_urlsafe(32)}
    ).json() == {"status": "missing"}
    assert (
        repo.database_path.read_bytes() == before
        and repo.ai_usage(user.user_id, now=snapshot_time) == usage
        and calls == []
    )
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "UPDATE coach_turns SET created_at=? WHERE nonce=?",
            (int(time()) - PENDING_LIFETIME, nonce),
        )
    before = repo.database_path.read_bytes()
    assert client.get("/web/coach/status", params={"nonce": nonce}).json() == {
        "status": "expired"
    }
    assert repo.database_path.read_bytes() == before
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT status FROM coach_turns WHERE nonce=?", (nonce,)
            ).fetchone()[0]
            == "pending"
        )


def test_status_after_real_handler_completion_does_not_duplicate_message_or_ai_call(
    setup,
):
    _, client, user, calls, directory = setup
    login(client)
    values = form(client)
    assert client.post("/web/coach/message", data=values).status_code == 200
    repo = CoachRepository(directory / "coach_conversations.db")
    before = repo.database_path.read_bytes()
    for _ in range(3):
        assert client.get(
            "/web/coach/status", params={"nonce": values["nonce"]}
        ).json() == {"status": "complete"}
    assert len(calls) == 1 and len(repo.view(user.user_id)["turns"]) == 1
    assert repo.database_path.read_bytes() == before


def test_failed_message_has_safe_reedit_control_and_original_text_not_an_automatic_resend(
    setup, monkeypatch
):
    _, client, user, calls, directory = setup
    login(client)

    def broken(*a, **k):
        raise RuntimeError("private provider body and key")

    monkeypatch.setattr(
        account_pages,
        "send_dialogue",
        lambda repository, user_id, text, nonce, **kwargs: send_dialogue(
            repository, user_id, text, nonce, **{**kwargs, "responder": broken}
        ),
    )
    values = form(client)
    values["message"] = "<script>alert(1)</script>\n请保留缩进。"
    response = client.post("/web/coach/message", data=values)
    assert response.status_code == 200 and "放回输入框修改" in response.text
    assert "&lt;script&gt;" in response.text and "<script>alert" not in response.text
    assert "private provider" not in response.text
    assert client.get(
        "/web/coach/status", params={"nonce": values["nonce"]}
    ).json() == {"status": "failed"}
    repo = CoachRepository(directory / "coach_conversations.db")
    assert len(repo.view(user.user_id)["turns"]) == 1 and calls == []
    assert (
        "nonce"
        not in client.get("/web/coach/history", params={"before": "999999"}).json()[
            "turns"
        ][0]
    )


def test_failed_reedit_is_disabled_while_another_reply_is_pending(setup):
    _, client, user, _, directory = setup
    login(client)
    repo = CoachRepository(directory / "coach_conversations.db")
    stamp = int(time())
    failed, pending = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    repo.claim(user.user_id, failed, "失败消息", now=stamp)
    repo.fail(user.user_id, failed, now=stamp)
    repo.claim(user.user_id, pending, "仍在处理", now=stamp)
    response = client.get("/web/welcome")
    assert 'class="dialogue-recover" type="button" disabled' in response.text
    assert "教练正在回复" in response.text


def test_status_is_owned_even_when_another_account_knows_the_request_nonce(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo = CoachRepository(directory / "coach_conversations.db")
    nonce = secrets.token_urlsafe(32)
    repo.claim("other-user", nonce, "他人的正文", now=int(time()))
    response = client.get("/web/coach/status", params={"nonce": nonce})
    assert (
        response.status_code == 200
        and response.json() == {"status": "missing"}
        and calls == []
    )
    assert "他人" not in response.text and repo.view(user.user_id)["turns"] == []


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"nonce": "short"},
        {"nonce": "x" * 44},
        {"nonce": "x" * 42 + "\n"},
        [("nonce", "x" * 43), ("nonce", "x" * 43)],
        {"nonce": "x" * 43, "user_id": "another"},
    ],
)
def test_status_rejects_malformed_or_ambiguous_parameters(setup, params):
    _, client, _, calls, _ = setup
    login(client)
    assert (
        client.get("/web/coach/status", params=params).status_code == 400
        and calls == []
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://other.invalid"},
        {"sec-fetch-site": "cross-site"},
        {"origin": "null", "sec-fetch-site": "cross-site"},
    ],
)
def test_status_requires_same_origin_metadata(setup, headers):
    _, client, _, _, _ = setup
    login(client)
    assert (
        client.get(
            "/web/coach/status", params={"nonce": "x" * 43}, headers=headers
        ).status_code
        == 403
    )


def test_guest_expired_session_and_internal_error_return_fixed_json(setup, monkeypatch):
    _, client, _, _, _ = setup
    assert (
        client.get("/web/coach/status", params={"nonce": "x" * 43}).status_code == 401
    )
    login(client)

    def broken(*a, **k):
        raise sqlite3.OperationalError("private path")

    monkeypatch.setattr(CoachRepository, "dialogue_status", broken)
    failed = client.get("/web/coach/status", params={"nonce": "x" * 43})
    assert failed.status_code == 503 and "private path" not in failed.text
    client.cookies.clear()
    assert (
        client.get("/web/coach/status", params={"nonce": "x" * 43}).status_code == 401
    )


def test_status_check_has_separate_bounded_rate_limit_and_does_not_send(setup):
    _, client, _, calls, _ = setup
    login(client)
    for _ in range(20):
        assert (
            client.get("/web/coach/status", params={"nonce": "x" * 43}).status_code
            == 200
        )
    limited = client.get("/web/coach/status", params={"nonce": "x" * 43})
    assert (
        limited.status_code == 429
        and int(limited.headers["retry-after"]) > 0
        and calls == []
    )


def test_reading_failed_status_works_without_ai_but_reedit_is_disabled(setup):
    _, _, user, calls, directory = setup
    repo = CoachRepository(directory / "coach_conversations.db")
    nonce = secrets.token_urlsafe(32)
    repo.claim(user.user_id, nonce, "之前未完成的消息", now=int(time()))
    repo.fail(user.user_id, nonce, now=int(time()))
    with TestClient(create_account_app(directory), base_url=BASE) as client:
        login(client)
        assert client.get("/web/coach/status", params={"nonce": nonce}).json() == {
            "status": "failed"
        }
        assert (
            'class="dialogue-recover" type="button" disabled'
            in client.get("/web/welcome").text
        )
    assert calls == []
