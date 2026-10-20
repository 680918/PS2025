import sqlite3

import pytest
from fastapi.testclient import TestClient

from tests import test_web_lesson_revision as base
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def test_source_question_round_trip_keeps_latest_lesson_and_current_learning(setup):
    _, client, repo, user, identity = setup
    item = repo.knowledge(user.user_id, identity)
    source = "/web/conversations/" + str(item["turn_id"])
    repo.create_topic(user.user_id, "当前学习位置保持原样")
    assert (
        repo.revise_knowledge(
            user.user_id,
            identity,
            1,
            title="修订后的当前教案",
            content="新版知识点",
            now=2000,
        )
        == "updated"
    )
    before = repo.database_path.read_bytes()
    page = client.get("/web/knowledge/" + identity)
    assert page.status_code == 200 and source in Links(page.text).links
    assert (
        '<details class="library-card lesson-origin"><summary>整理来源 · ' in page.text
    )
    assert "整理时的提问 · 已回复" in page.text and "整理教案" in page.text
    assert "1970-01-01 08:16" in page.text
    original = client.get(source)
    assert original.status_code == 200 and "请确认草稿。" in original.text
    assert "这轮讨论留下的教案" in original.text and "修订后的当前教案" in original.text
    assert "/web/knowledge/" + identity in Links(original.text).links
    returned = client.get("/web/knowledge/" + identity)
    assert "当前为第 2 版" in returned.text and "新版知识点" in returned.text
    assert repo.active_topic(user.user_id)["title"] == "当前学习位置保持原样"
    assert repo.database_path.read_bytes() == before
    with sqlite3.connect(repo.database_path) as db:
        assert db.execute("SELECT count(*) FROM coach_ai_usage").fetchone()[0] == 0


def test_pending_draft_can_trace_source_without_becoming_saved(setup):
    _, client, repo, user, _ = setup
    draft = saved_lesson(repo, user.user_id, title="尚待确认", save=False)
    origin = repo.knowledge_origin(user.user_id, draft)
    before = repo.database_path.read_bytes()
    page = client.get("/web/knowledge/" + draft)
    assert page.status_code == 200 and "整理来源" in page.text
    response = client.get("/web/conversations/" + str(origin["turn_id"]))
    assert response.status_code == 200 and "待你确认的草稿" in response.text
    assert repo.knowledge(user.user_id, draft)["status"] == "pending"
    assert repo.database_path.read_bytes() == before


def test_source_excerpt_is_escaped_bounded_and_complete_question_remains_available(
    setup,
):
    _, client, repo, user, identity = setup
    item = repo.knowledge(user.user_id, identity)
    question = "<img src=x onerror=alert(1)>\n" + "回想练习" * 100 + "问题末尾独有内容"
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_turns SET user_content=? WHERE turn_id=?",
            (question, item["turn_id"]),
        )
    page = client.get("/web/knowledge/" + identity)
    assert (
        "&lt;img src=x onerror=alert(1)&gt;" in page.text
        and "<img src=x" not in page.text
    )
    assert "问题末尾独有内容" not in page.text and "…</p>" in page.text
    complete = client.get("/web/conversations/" + str(item["turn_id"]))
    assert "问题末尾独有内容" in complete.text and "<img src=x" not in complete.text


@pytest.mark.parametrize("kind", ["missing", "foreign"])
def test_unavailable_source_keeps_lesson_without_link_or_private_disclosure(
    setup, kind
):
    _, client, repo, user, identity = setup
    foreign = saved_lesson(
        repo,
        "someone-else",
        title="PRIVATE_FOREIGN_LESSON",
        content="PRIVATE_FOREIGN_BODY",
    )
    foreign_turn = repo.knowledge("someone-else", foreign)["turn_id"]
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_turns SET user_content=? WHERE turn_id=?",
            ("PRIVATE_FOREIGN_QUESTION", foreign_turn),
        )
        db.execute(
            "UPDATE coach_knowledge SET turn_id=? WHERE knowledge_id=?",
            (foreign_turn if kind == "foreign" else foreign_turn + 999, identity),
        )
    before = repo.database_path.read_bytes()
    page = client.get("/web/knowledge/" + identity)
    assert page.status_code == 200 and "原始整理对话暂不可用" in page.text
    assert "原版教案" in page.text and "原始依据" in page.text
    assert "PRIVATE_FOREIGN" not in page.text
    assert not any(
        url.startswith("/web/conversations/") for url in Links(page.text).links
    )
    assert repo.database_path.read_bytes() == before


def test_visitors_and_other_accounts_cannot_use_lesson_to_find_origin(setup):
    app, _, repo, user, identity = setup
    with TestClient(app, base_url=BASE) as stranger:
        assert (
            stranger.get(
                "/web/knowledge/" + identity, follow_redirects=False
            ).status_code
            == 303
        )
        login(stranger, "two@example.com")
        response = stranger.get("/web/knowledge/" + identity)
        assert response.status_code == 404 and "整理教案" not in response.text
        source = repo.knowledge_origin(user.user_id, identity)
        assert (
            stranger.get("/web/conversations/" + str(source["turn_id"])).status_code
            == 404
        )


def test_origin_error_is_generic_and_following_read_can_recover(setup, monkeypatch):
    _, client, repo, _, identity = setup
    original = type(repo).knowledge_origin

    def broken(*a):
        raise sqlite3.OperationalError("SECRET_INTERNAL_LOCATION")

    monkeypatch.setattr(type(repo), "knowledge_origin", broken)
    page = client.get("/web/knowledge/" + identity)
    assert page.status_code == 503 and "SECRET_INTERNAL_LOCATION" not in page.text
    monkeypatch.setattr(type(repo), "knowledge_origin", original)
    assert client.get("/web/knowledge/" + identity).status_code == 200
