import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from tests import test_web_coach_dialogue as base
from tests import test_web_unit_lessons as units
from tests import test_web_studies as studies
from tests.test_ai_usage import limits, send
from tests.test_web_coach_dialogue import login, form, BASE
from conversation.coach_repository import CoachRepository

setup = base.setup
password_hash = base.password_hash
no_external_services = base.no_external_services
unit_setup = units.setup
study_setup = studies.setup


@pytest.fixture
def repository(tmp_path, setup):
    return CoachRepository(tmp_path / "coach_conversations.db")


def test_daily_rejection_returns_known_unsent_json_without_model_calls(
    setup, repository
):
    _, client, calls, user, _ = setup
    login(client)
    limits(repository, user=0, total=0)
    values = {**form(client), "message": "这段输入需要保留，不能丢失。"}
    before = repository.database_path.read_bytes()
    result = client.post(
        "/web/coach/message", data=values, headers={"accept": "application/json"}
    )
    assert result.status_code == 429 and result.json()["code"] == "daily_ai_limit"
    assert result.json()["sent"] is False and "未调用 AI" in result.json()["error"]
    assert calls == [] and repository.database_path.read_bytes() == before
    assert repository.view(user.user_id)["turns"] == []
    plain = client.post("/web/coach/message", data=values)
    assert plain.status_code == 429 and "当前已暂停" in plain.text


def test_success_and_duplicate_share_one_admission_and_usage_page_is_owned(
    setup, repository, tmp_path
):
    app, client, calls, user, _ = setup
    login(client)
    values = form(client)
    assert client.post("/web/coach/message", data=values).status_code == 200
    assert client.post("/web/coach/message", data=values).status_code == 200
    assert len(calls) == 1 and repository.ai_usage(user.user_id)["used"] == 1
    before = repository.database_path.read_bytes()
    usage = client.get("/web/usage?user_id=someone&per_user=99999")
    assert (
        usage.status_code == 200 and "已受理 <strong>1</strong> / 100 次" in usage.text
    )
    assert "不是实际账单" in usage.text and "聊天、续学与对话教案" in usage.text
    assert repository.database_path.read_bytes() == before
    assert client.post("/web/usage", data={"per_user": 99999}).status_code == 405
    assert 'href="/web/usage"' in client.get("/web/welcome").text
    assert usage.headers["cache-control"] == "no-store"
    with TestClient(app, base_url=BASE) as anonymous:
        assert anonymous.get("/web/usage", follow_redirects=False).status_code == 303


def test_memory_save_is_still_free_while_ai_is_paused(setup, repository):
    _, client, calls, user, _ = setup
    login(client)
    limits(repository, user=0, total=0)
    result = client.post(
        "/web/coach/message",
        data={**form(client), "message": "请记住，喜欢结合日常例子学习。"},
    )
    assert result.status_code == 200 and calls == []
    assert (
        repository.list_memories(user.user_id)
        and repository.ai_usage(user.user_id)["used"] == 0
    )


def test_unit_summary_and_normal_chat_use_the_same_daily_limit(unit_setup):
    client, repo, _, user, book, unit, calls = unit_setup
    limits(repo, user=1)
    assert client.post("/web/coach/message", data=form(client)).status_code == 200
    path, values, _ = units.form(client, book, unit)
    before = repo.database_path.read_bytes()
    denied = client.post(path, data=values)
    assert denied.status_code == 429 and "个人上限" in denied.text
    assert "/web/usage" in denied.text and "返回单元整理" in denied.text
    assert len(calls) == 1 and repo.database_path.read_bytes() == before
    assert repo.unit_lesson_result(user.user_id, values["nonce"]) is None


def test_study_resume_does_not_switch_or_call_when_limit_is_reached(study_setup):
    _, client, repo, _, user, _, calls = study_setup
    login(client)
    studies.create(client, "主题甲")
    a = repo.active_topic(user.user_id)["topic_id"]
    studies.create(client, "主题乙")
    b = repo.active_topic(user.user_id)["topic_id"]
    limits(repo, user=0)
    result = studies.choose(client, a, "continue")
    assert result.status_code == 429 and "未调用 AI" in result.text
    assert repo.active_topic(user.user_id)["topic_id"] == b and calls == []


def test_usage_page_never_lists_other_accounts_and_shared_limit_is_generic(unit_setup):
    client, repo, _, user, _, _, _ = unit_setup
    limits(repo, user=1, total=1)
    from time import time

    assert send(repo, user="other-private-user", now=int(time())) == "complete"
    page = client.get("/web/usage")
    assert "本成长空间今天的 AI 请求额度已用尽" in page.text
    assert "本次尚未受理" not in page.text and "新的 AI 请求暂不受理" in page.text
    assert (
        "已受理 <strong>0</strong>" in page.text
        and "other-private-user" not in page.text
    )
    assert "这里还没有受理记录" in page.text


def test_forged_requests_and_unavailable_usage_storage_do_not_invoke_model(
    setup, repository, monkeypatch
):
    _, client, calls, _, _ = setup
    login(client)
    values = {**form(client), "csrf": "0" * 64}
    assert client.post("/web/coach/message", data=values).status_code == 403
    assert calls == []

    def broken(*a, **k):
        raise sqlite3.OperationalError("private credentials path")

    monkeypatch.setattr(CoachRepository, "ai_usage", broken)
    result = client.get("/web/usage")
    assert result.status_code == 503 and "private credentials" not in result.text


def test_shared_budget_schema_does_not_capture_message_text_or_keys(setup, repository):
    _, client, _, user, _ = setup
    login(client)
    client.post(
        "/web/coach/message",
        data={**form(client), "message": "这是不会写进用量表的原话"},
    )
    with closing(repository._connect()) as db:
        row = dict(db.execute("SELECT * FROM coach_ai_usage").fetchone())
    assert set(row) == {"user_id", "nonce", "day", "kind", "started_at"}
    assert row["user_id"] == user.user_id and "原话" not in str(row)
