import sqlite3
from time import time
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from conversation.coach_repository import CoachRepository
from tests import test_web_studies as base
from tests.test_conversation_review import turn, topic
from tests.test_growth_review import lesson
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_paid_services = base.no_paid_services


def test_growth_summary_links_and_reading_preserve_all_business_data(setup):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    now = int(time())
    first = topic(repo, "阅读与行动", user=user.user_id, now=now - 100)
    question = turn(repo, "怎样把阅读变成行动？", user=user.user_id, now=now - 90)
    identity = lesson(repo, user.user_id, title="回想与实践", saved_at=now - 80)
    last = topic(repo, "表达练习", user=user.user_id, now=now - 70)
    before = {p: p.read_bytes() for p in [repo.database_path, materials.database_path]}
    response = client.get("/web/growth")
    assert response.status_code == 200 and "成长回顾" in response.text
    assert "怎样把阅读变成行动？" in response.text and "回想与实践" in response.text
    links = Links(response.text).links
    assert "/web/conversations/" + str(question) in links
    assert "/web/knowledge/" + identity in links
    target = next(
        link for link in links if link.startswith("/web/conversations?topic=")
    )
    assert parse_qs(urlsplit(target).query)["topic"] == [first]
    assert client.get(target).status_code == 200
    assert client.get("/web/conversations/" + str(question)).status_code == 200
    assert client.get("/web/knowledge/" + identity).status_code == 200
    assert repo.active_topic(user.user_id)["topic_id"] == last
    assert all(p.read_bytes() == raw for p, raw in before.items()) and calls == []
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "成长回顾" in client.get("/web/welcome").text


def test_trial_navigation_uses_owned_active_topic_and_pending_lesson_without_writes(
    setup,
):
    _, client, repo, materials, user, _, calls = setup
    login(client)
    topic(repo, "我的长期主题", user=user.user_id, now=int(time()) - 10)
    lesson(repo, user.user_id, title="等待确认的教案", save=False)
    before = {p: p.read_bytes() for p in [repo.database_path, materials.database_path]}
    response = client.get("/web/growth")
    links = Links(response.text).links
    assert response.status_code == 200 and "个人试用导航" in response.text
    assert "继续当前主题" in response.text and "我的长期主题" in response.text
    assert "查看待确认教案" in response.text
    assert {
        "/web/welcome",
        "/web/materials",
        "/web/knowledge?status=pending",
        "/web/export",
    } <= set(links)
    assert "不会调用 AI、改变学习位置或把浏览算作学习完成" in response.text
    assert all(p.read_bytes() == raw for p, raw in before.items()) and calls == []


def test_trial_navigation_is_private_and_escapes_active_topic(setup):
    app, client, repo, _, user, _, calls = setup
    login(client)
    topic(repo, "<script>仅本人主题</script>", user=user.user_id, now=int(time()) - 5)
    own = client.get("/web/growth")
    assert "&lt;script&gt;仅本人主题&lt;/script&gt;" in own.text
    client.cookies.clear()
    login(client, "two@example.com")
    other = client.get("/web/growth")
    assert "仅本人主题" not in other.text and "从对话开始" in other.text
    with TestClient(app, base_url=BASE) as guest:
        assert guest.get("/web/growth", follow_redirects=False).status_code == 303
    assert calls == []


def test_empty_periods_and_all_time_selection_are_clear_and_no_ai(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    turn(repo, "多年前的完整讨论", user=user.user_id, now=1000)
    week = client.get("/web/growth?period=7")
    assert "从一个问题开始" in week.text and "多年前的完整讨论" not in week.text
    assert client.get("/web/growth?period=30").status_code == 200
    all_time = client.get("/web/growth?period=all")
    assert "多年前的完整讨论" in all_time.text and "全部已有记录" in all_time.text
    assert "不代表学习时长、完成程度或掌握水平" in all_time.text
    assert 'href="?period=all" aria-current="page"' in all_time.text
    assert 'href="?period=7" aria-current="page"' in week.text
    assert "本期还没有确认保存的教案" in all_time.text and calls == []


def test_private_access_and_session_expiry_do_not_leak_summary(setup):
    app, client, repo, _, user, _, calls = setup
    login(client)
    turn(repo, "本人独有问题", user=user.user_id, now=int(time()) - 5)
    lesson(repo, user.user_id, title="本人私有教案", saved_at=int(time()) - 4)
    with TestClient(app, base_url=BASE) as guest:
        response = guest.get("/web/growth", follow_redirects=False)
        assert (
            response.status_code == 303 and response.headers["location"] == "/web/login"
        )
        assert "本人私有教案" not in response.text
    client.cookies.clear()
    login(client, "two@example.com")
    other = client.get("/web/growth")
    assert "本人私有教案" not in other.text and "本人独有问题" not in other.text
    assert "从一个问题开始" in other.text and calls == []


@pytest.mark.parametrize(
    "query",
    [
        "period=90",
        "period=",
        "period=7&period=30",
        "period=%3Cscript%3E",
        "period=" + "x" * 500,
    ],
)
def test_invalid_and_duplicate_periods_are_rejected(setup, query):
    _, client, repo, _, _, _, calls = setup
    login(client)
    before = repo.database_path.read_bytes()
    response = client.get("/web/growth?" + query)
    assert response.status_code == 400 and "<script>" not in response.text
    assert repo.database_path.read_bytes() == before and calls == []


def test_titles_questions_and_metadata_are_escaped_and_not_interpreted(setup):
    _, client, repo, _, user, _, calls = setup
    login(client)
    now = int(time())
    topic(repo, "<script>主题</script>", user=user.user_id, now=now - 100)
    turn(repo, "<img src=x onerror=alert(1)>问题", user=user.user_id, now=now - 90)
    lesson(repo, user.user_id, title="<script>教案</script>", saved_at=now - 80)
    response = client.get("/web/growth")
    assert "&lt;script&gt;主题&lt;/script&gt;" in response.text
    assert "&lt;script&gt;教案&lt;/script&gt;" in response.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in response.text
    assert Links(response.text).active == [] and calls == []


def test_database_errors_are_fixed_and_do_not_mutate_records(setup, monkeypatch):
    _, client, repo, _, _, _, calls = setup
    login(client)
    before = repo.database_path.read_bytes()

    def broken(*a, **k):
        raise sqlite3.OperationalError("private database path")

    monkeypatch.setattr(CoachRepository, "growth_review", broken)
    response = client.get("/web/growth")
    assert response.status_code == 503 and "private database path" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert repo.database_path.read_bytes() == before and calls == []


def test_growth_view_is_rate_limited_without_model_calls(setup):
    _, client, _, _, _, _, calls = setup
    login(client)
    for _ in range(40):
        assert client.get("/web/growth").status_code == 200
    denied = client.get("/web/growth")
    assert denied.status_code == 429 and int(denied.headers["retry-after"]) > 0
    assert calls == []
