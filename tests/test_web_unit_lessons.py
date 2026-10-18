import secrets
import sqlite3
from time import time
from uuid import uuid4
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from coach.dialogue import CoachAnswer
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from tests import test_web_book_section as base_tests
from tests.test_web_coach_dialogue import Forms, login, add_user, BASE

password_hash = base_tests.password_hash
no_real_services = base_tests.no_real_services


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "单元教案体验者")
    add_user(tmp_path, password_hash, "two@example.com", "另一位用户")
    materials = MaterialRepository(tmp_path / "coach_library.db")
    book = materials.add(
        user.user_id, "a.txt", ("甲" * 2400).encode(), title="<单元资料>"
    )
    repo = CoachRepository(tmp_path / "coach_conversations.db", materials=materials)
    unit = uuid4().hex
    repo.save_book_unit(user.user_id, book, unit, "<第一单元>", 1, 3, 0)
    for chunk in materials.chunks(user.user_id, book)[:2]:
        nonce = secrets.token_urlsafe(32)
        repo.claim(user.user_id, nonce, "已讲解", now=int(time()))
        repo.finish(
            user.user_id,
            nonce,
            "本段讲解",
            None,
            now=int(time()),
            material_id=book,
            part_id=chunk["chunk_id"],
            explained_part=True,
        )
    repo.create_topic(user.user_id, "Python 入门")
    calls = []

    def respond(history, message, learning, *, context):
        calls.append(context)
        return CoachAnswer(
            "草稿已生成。",
            used_source_ids=[row["source_id"] for row in context["sources"]],
            knowledge_draft={
                "title": "本单元复习教案",
                "topic": "单元",
                "content": "## 复习提纲\n核心知识、例子与练习建议。",
            },
        )

    app = create_account_app(tmp_path, dialogue_responder=respond)
    with TestClient(app, base_url=BASE) as client:
        login(client)
        yield client, repo, materials, user, book, unit, calls


def form(client, book, unit):
    path = f"/web/materials/{book}/plan/{unit}/lessons"
    page = client.get(path)
    return path, Forms(page.text).values(path), page


def test_preview_generate_confirm_and_find_from_unit(setup):
    client, repo, _, user, book, unit, calls = setup
    active = repo.active_topic(user.user_id)
    path, fields, page = form(client, book, unit)
    assert page.status_code == 200 and calls == [] and "2 / 3" in page.text
    assert "&lt;第一单元&gt;" in page.text
    assert "片段 1" in page.text and "片段 2" in page.text
    assert "data-unit-submit" in page.text and "unit-lessons.js" in page.text
    assert (
        'href="#unit-lesson-assets"' in page.text
        and 'id="unit-lesson-assets"' in page.text
    )
    generated = client.post(path, data=fields)
    assert generated.status_code == 200 and "待确认草稿" in generated.text
    assert "整理范围说明" in generated.text and "片段 1、片段 2" in generated.text
    assert len(calls) == 1 and len(calls[0]["sources"]) == 2
    assert repo.active_topic(user.user_id) == active
    assert len(repo.book_coverage(user.user_id, book)) == 2
    identity = repo.unit_lesson_result(user.user_id, fields["nonce"])
    assert repo.knowledge(user.user_id, identity)["status"] == "pending"
    assert client.post(path, data=fields).status_code == 200 and len(calls) == 1
    save_path = f"/web/knowledge/{identity}/save"
    values = Forms(generated.text).values(save_path)
    values["content"] = repo.knowledge(user.user_id, identity)["content"]
    assert client.post(save_path, data=values).status_code == 200
    directory = client.get(f"/web/materials/{book}/plan")
    assert "本单元复习教案" in directory.text and "已保存" in directory.text
    summary_page = client.get(path)
    assert (
        "查看已有教案" in summary_page.text and "重新整理本批草稿" in summary_page.text
    )
    downloaded = client.get(f"/web/knowledge/{identity}/download")
    assert downloaded.status_code == 200 and "整理范围说明" in downloaded.text
    assert "第 1 / 1 批" in downloaded.text
    assert len(calls) == 1


@pytest.mark.parametrize(
    "bad",
    ["csrf", "batch", "digest", "nonce", "origin", "extra", "duplicate", "oversize"],
)
def test_forged_summary_requests_never_call_ai_or_create_assets(setup, bad):
    client, repo, _, user, book, unit, calls = setup
    path, fields, _ = form(client, book, unit)
    headers = {}
    if bad == "csrf":
        fields["csrf"] = "0" * 64
    if bad == "batch":
        fields["batch"] = "2"
    if bad == "digest":
        fields["digest"] = "0" * 64
    if bad == "nonce":
        fields["nonce"] = secrets.token_urlsafe(32)
    if bad == "origin":
        headers["origin"] = "https://evil.example"
    if bad == "extra":
        fields["user_id"] = user.user_id
    if bad == "oversize":
        fields["digest"] = "0" * 5000
    if bad == "duplicate":
        result = client.post(
            path,
            content=urlencode(fields) + "&batch=2",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    else:
        result = client.post(path, data=fields, headers=headers)
    assert result.status_code in {400, 403}
    assert calls == [] and repo.unit_knowledge(user.user_id, book, unit) == []


def test_stale_unit_or_coverage_requires_new_preflight(setup):
    client, repo, materials, user, book, unit, calls = setup
    path, fields, _ = form(client, book, unit)
    repo.save_book_unit(user.user_id, book, unit, "新名称", 1, 3, 1)
    assert client.post(path, data=fields).status_code == 409 and calls == []
    _, new, _ = form(client, book, unit)
    with sqlite3.connect(repo.database_path) as db:
        chunk = materials.chunks(user.user_id, book)[0]
        db.execute(
            "DELETE FROM coach_book_coverage WHERE chunk_id=?", (chunk["chunk_id"],)
        )
    assert client.post(path, data=new).status_code == 409 and calls == []


def test_busy_is_shared_with_chat_and_accounts_are_isolated(setup):
    client, repo, _, user, book, unit, calls = setup
    path, fields, _ = form(client, book, unit)
    repo.claim(user.user_id, secrets.token_urlsafe(32), "pending", now=int(time()))
    assert client.post(path, data=fields).status_code == 409 and calls == []
    client.cookies.clear()
    login(client, "two@example.com")
    assert client.get(path).status_code == 404
    assert client.post(path, data=fields).status_code == 403


def test_no_explained_scope_shows_guidance_without_ai(setup):
    client, repo, _, user, book, _, calls = setup
    unit = uuid4().hex
    # Use a different owned material because units may not overlap.
    materials = MaterialRepository(repo.database_path.parent / "coach_library.db")
    other = materials.add(user.user_id, "b.txt", "尚未讲解的资料".encode())
    repo.save_book_unit(user.user_id, other, unit, "新单元", 1, 1, 0)
    page = client.get(f"/web/materials/{other}/plan/{unit}/lessons")
    assert page.status_code == 200 and "先从一次讲解开始" in page.text
    assert "data-unit-submit" not in page.text and calls == []


def test_opaque_same_origin_form_works(setup):
    client, _, _, _, book, unit, calls = setup
    path, fields, _ = form(client, book, unit)
    assert (
        client.post(
            path,
            data=fields,
            headers={"origin": "null", "sec-fetch-site": "cross-site"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path,
            data=fields,
            headers={"origin": "null", "sec-fetch-site": "same-origin"},
        ).status_code
        == 200
    )
    assert len(calls) == 1
