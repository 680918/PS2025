import sqlite3
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from coach.learning_topics import TopicBusy
from conversation.coach_repository import CoachRepository
from tests import test_web_library as base
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import BASE, login, Forms, form, add_user

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def start(client, user, directory):
    repo = CoachRepository(directory / "coach_conversations.db")
    identity = saved_lesson(repo, user=user.user_id)
    path = "/web/knowledge/" + identity
    html = client.get(path).text
    page = client.post(path + "/review", data=Forms(html).values(path + "/review"))
    assert page.status_code == 200
    return repo, identity, page.text, Forms(page.text).values("/web/review/end")


def test_current_review_visible_and_end_returns_to_original_topic_without_ai(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, html, values = start(client, user, directory)
    assert "继续重温教案" in html and "教案整理时的引用" in html
    assert "结束重温，继续主题学习" in html
    topic = repo.active_topic(user.user_id)
    usage = repo.ai_usage(user.user_id)
    page = client.post("/web/review/end", data=values)
    assert page.status_code == 200 and "结束重温，继续主题学习" not in page.text
    assert "继续上次学习" in page.text
    assert (
        repo.review(user.user_id) is None and repo.active_topic(user.user_id) == topic
    )
    assert repo.ai_usage(user.user_id)["used"] == usage["used"] and calls == []
    assert repo.knowledge(user.user_id, identity)["status"] == "saved"
    assert client.post("/web/review/end", data=values).status_code == 409


def test_old_composer_before_and_after_end_is_refused_without_ai_or_new_turn(setup):
    _, client, user, calls, directory = setup
    login(client)
    old = form(client)
    repo, identity, html, values = start(client, user, directory)
    during = Forms(html).values("/web/coach/message", "message")
    before = repo.view(user.user_id)["turns"]
    assert (
        client.post(
            "/web/coach/message", data={**old, "message": "旧的普通页"}
        ).status_code
        == 409
    )
    assert client.post("/web/review/end", data=values).status_code == 200
    denied = client.post("/web/coach/message", data={**during, "message": "旧的重温页"})
    assert denied.status_code == 409 and "本次未发送" in denied.text
    assert "readonly" in denied.text and "旧的重温页" in denied.text
    assert repo.view(user.user_id)["turns"] == before and calls == []
    # A freshly loaded ordinary composer still works.
    assert (
        client.post(
            "/web/coach/message", data={**form(client), "message": "新的普通问题"}
        ).status_code
        == 200
    )
    assert len(calls) == 1 and calls[0]["review"] is None


def test_async_stale_message_reports_unsent_and_has_no_ai_side_effect(setup):
    _, client, user, calls, directory = setup
    login(client)
    before = form(client)
    repo, _, _, _ = start(client, user, directory)
    turns = repo.view(user.user_id)["turns"]
    response = client.post(
        "/web/coach/message",
        data={**before, "message": "保留输入"},
        headers={"accept": "application/json"},
    )
    assert (
        response.status_code == 409
        and response.json()["code"] == "review_state_changed"
    )
    assert response.json()["sent"] is False and "输入仍保留" in response.json()["error"]
    assert calls == [] and repo.view(user.user_id)["turns"] == turns


def test_old_exit_cannot_end_a_reselected_lesson_and_guard_fields_are_signed(setup):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, html, values = start(client, user, directory)
    repo.select_review(user.user_id, identity)
    assert client.post("/web/review/end", data=values).status_code == 409
    message = Forms(html).values("/web/coach/message", "message")
    for change in [
        {"review_id": ""},
        {"review_revision": "999"},
        {"review_revision": "-1"},
    ]:
        assert (
            client.post(
                "/web/coach/message", data={**message, **change, "message": "不能发送"}
            ).status_code
            == 403
        )
    assert repo.review(user.user_id)["knowledge_id"] == identity and calls == []


@pytest.mark.parametrize(
    "kind", ["csrf", "revision", "identity", "origin", "json", "duplicate", "extra"]
)
def test_exit_form_scope_is_checked(setup, kind):
    _, client, user, calls, directory = setup
    login(client)
    repo, identity, _, values = start(client, user, directory)
    kwargs = {"data": values}
    if kind == "csrf":
        kwargs = {"data": {**values, "csrf": "0" * 64}}
    elif kind == "revision":
        kwargs = {"data": {**values, "revision": "999"}}
    elif kind == "identity":
        kwargs = {"data": {**values, "knowledge_id": "a" * 32}}
    elif kind == "origin":
        kwargs["headers"] = {"origin": "https://foreign.invalid"}
    elif kind == "json":
        kwargs = {"json": values}
    elif kind == "duplicate":
        kwargs = {
            "content": urlencode(values) + "&revision=1",
            "headers": {"content-type": "application/x-www-form-urlencoded"},
        }
    elif kind == "extra":
        kwargs = {"data": {**values, "user_id": "other"}}
    assert client.post("/web/review/end", **kwargs).status_code == 403
    assert repo.review(user.user_id)["knowledge_id"] == identity and calls == []


def test_exit_guest_other_account_busy_and_database_error_are_safe(
    setup, password_hash, monkeypatch
):
    app, client, user, calls, directory = setup
    login(client)
    repo, identity, _, values = start(client, user, directory)
    with TestClient(app, base_url=BASE) as guest:
        assert (
            guest.post(
                "/web/review/end", data=values, follow_redirects=False
            ).status_code
            == 303
        )
    add_user(directory, password_hash, "two@example.com", "另一位虚构用户")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        assert other.post("/web/review/end", data=values).status_code == 403

    def busy(*a, **k):
        raise TopicBusy("教练还在回复，请稍后。")

    monkeypatch.setattr(CoachRepository, "end_review", busy)
    assert client.post("/web/review/end", data=values).status_code == 409

    def broken(*a, **k):
        raise sqlite3.OperationalError("private path")

    monkeypatch.setattr(CoachRepository, "end_review", broken)
    response = client.post("/web/review/end", data=values)
    assert response.status_code == 503 and "private path" not in response.text
    assert repo.review(user.user_id)["knowledge_id"] == identity and calls == []
