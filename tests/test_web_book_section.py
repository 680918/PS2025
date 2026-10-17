import io
import secrets
import sqlite3
import smtplib
from time import time

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from coach.dialogue import CoachAnswer
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_web_coach_dialogue import add_user, login, Forms, PASSWORD, BASE
from tests.test_coach_materials import pdf_bytes


@pytest.fixture(autouse=True)
def no_real_services(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No real SMTP or AI in book study tests")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "选段学习体验者")
    other = add_user(tmp_path, password_hash, "two@example.com", "其他用户")
    materials = MaterialRepository(tmp_path / "coach_library.db")
    book = materials.add(
        user.user_id,
        "notes.txt",
        ("甲" * 800 + "乙" * 800 + "丙" * 800).encode(),
        title="<书籍标题>",
    )
    calls = []

    def respond(history, message, learning, *, context):
        calls.append(context)
        return CoachAnswer(
            "本段的讲解。",
            {
                "topic": "模型不应改名",
                "progress": "已讨论所选段落",
                "next_step": "结合例子",
            },
            [item["source_id"] for item in context["sources"]],
            {
                "title": "选段教案",
                "topic": learning["topic"],
                "content": "本段教案内容。",
            }
            if context["draft_requested"]
            else None,
        )

    app = create_account_app(tmp_path, dialogue_responder=respond)
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    with TestClient(app, base_url=BASE) as client:
        login(client)
        yield app, client, repo, materials, user, other, book, calls


def choose(client, book, part=2):
    path = "/web/materials/" + book
    form = Forms(client.get(path + f"?part={part}").text).values(path + "/study")
    return client.post(path + "/study", data=form)


def test_choose_then_explain_and_request_lesson_use_same_chat_and_exact_part(setup):
    _, client, repo, materials, user, _, book, calls = setup
    chosen = choose(client, book)
    assert chosen.status_code == 200 and calls == []
    assert "当前选段 · 片段 2" in chosen.text and "讲解并提炼这段" in chosen.text
    assert "&lt;书籍标题&gt;" in chosen.text
    path = "/web/coach/message"
    fields = Forms(chosen.text).values(path, "study")
    assert fields["part_id"] == materials.chunks(user.user_id, book)[1]["chunk_id"]
    answer = client.post(path, data=fields)
    assert answer.status_code == 200 and len(calls) == 1
    assert (
        len(calls[0]["sources"]) == 1 and calls[0]["sources"][0]["locator"] == "片段 2"
    )
    assert repo.active_topic(user.user_id)["title"] == "研读《<书籍标题>》"
    assert client.post(path, data=fields).status_code == 200 and len(calls) == 1
    lesson = Forms(client.get("/web/welcome").text).values(path, "lesson")
    assert client.post(path, data=lesson).status_code == 200
    assert len(repo.list_knowledge(user.user_id, status="pending")) == 1
    assert repo.list_knowledge(user.user_id) == []
    assert "片段 2" in client.get("/web/studies").text


def test_old_workspace_form_cannot_be_tampered_and_can_resume_its_displayed_part(setup):
    _, client, repo, materials, user, _, book, calls = setup
    first = choose(client, book, 1)
    path = "/web/coach/message"
    fields = Forms(first.text).values(path, "message")
    choose(client, book, 3)
    new = materials.chunks(user.user_id, book)[2]["chunk_id"]
    assert (
        client.post(
            path, data={**fields, "part_id": new, "message": "解释这一段"}
        ).status_code
        == 403
    )
    assert (
        client.post(path, data={**fields, "message": "解释这一段"}).status_code == 200
    )
    assert calls[0]["sources"][0]["locator"] == "片段 1"
    assert repo.topic_part(user.user_id)["chunk_id"] == fields["part_id"]


@pytest.mark.parametrize(
    "kind",
    ["csrf", "part", "origin", "cross-site", "extra", "duplicate", "json", "oversize"],
)
def test_bad_selection_cannot_change_study_state(setup, kind):
    _, client, repo, _, user, _, book, calls = setup
    path = "/web/materials/" + book + "/study"
    fields = Forms(client.get("/web/materials/" + book).text).values(path)
    headers = {}
    if kind == "csrf":
        fields["csrf"] = "bad"
    if kind == "part":
        fields["chunk_id"] = "a" * 32
    if kind == "origin":
        headers["origin"] = "https://outside.example"
    if kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "extra":
        fields["user_id"] = user.user_id
    if kind == "oversize":
        fields["chunk_id"] = "a" * 5000
    if kind == "duplicate":
        result = client.post(
            path,
            content="csrf=x&csrf=y&chunk_id=z",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    elif kind == "json":
        result = client.post(path, json=fields)
    else:
        result = client.post(path, data=fields, headers=headers)
    assert result.status_code in {400, 403}
    assert repo.list_topics(user.user_id) == [] and calls == []


def test_other_users_and_sessions_cannot_use_part_or_read_material(setup):
    app, client, _, materials, _, other, book, calls = setup
    path = "/web/materials/" + book
    fields = Forms(client.get(path).text).values(path + "/study")
    with TestClient(app, base_url=BASE) as someone:
        assert someone.get(path, follow_redirects=False).status_code == 303
        login(someone, "two@example.com")
        assert someone.get(path).status_code == 404
        assert someone.post(path + "/study", data=fields).status_code == 403
    assert (
        materials.chunk(other.user_id, book, fields["chunk_id"]) is None and calls == []
    )


def test_busy_reply_blocks_selection_and_previewing_does_not_change_it(setup):
    _, client, repo, _, user, _, book, calls = setup
    choose(client, book, 1)
    old = repo.topic_part(user.user_id)["chunk_id"]
    repo.claim(user.user_id, secrets.token_urlsafe(32), "正在回复", now=int(time()))
    preview = client.get("/web/materials/" + book + "?part=3")
    fields = Forms(preview.text).values("/web/materials/" + book + "/study")
    assert (
        client.post("/web/materials/" + book + "/study", data=fields).status_code == 409
    )
    assert repo.topic_part(user.user_id)["chunk_id"] == old and calls == []


def pdf_with_blank_middle():
    from pypdf import PdfReader, PdfWriter

    page = PdfReader(io.BytesIO(pdf_bytes())).pages[0]
    output = PdfWriter()
    output.add_page(page)
    output.add_blank_page(width=300, height=200)
    output.add_page(page)
    raw = io.BytesIO()
    output.write(raw)
    return raw.getvalue()


def test_pdf_actual_page_navigation_blank_page_and_invalid_inputs(setup):
    _, client, repo, materials, user, _, _, calls = setup
    book = materials.add(user.user_id, "pages.pdf", pdf_with_blank_middle())
    path = "/web/materials/" + book
    third = client.get(path + "?page=3")
    assert third.status_code == 200 and "PDF 第 3 页" in third.text
    fields = Forms(third.text).values(path + "/study")
    assert client.post(path + "/study", data=fields).status_code == 200
    assert repo.topic_part(user.user_id)["chunk_id"] == fields["chunk_id"]
    blank = client.get(path + "?page=2")
    assert (
        blank.status_code == 200
        and "没有可提取的文字" in blank.text
        and "选中这段" not in blank.text
    )
    for query in ("?page=4", "?page=bad", "?part=bad"):
        assert client.get(path + query).status_code == 400
    assert (
        repo.topic_part(user.user_id)["chunk_id"] == fields["chunk_id"] and calls == []
    )


def test_ai_disabled_still_allows_browsing_selecting_and_position_restore(setup):
    _, _, repo, _, user, _, book, _ = setup
    app = create_account_app(repo.database_path.parent)
    with TestClient(app, base_url=BASE) as client:
        login(client)
        chosen = choose(client, book, 2)
        assert chosen.status_code == 200 and "当前选段 · 片段 2" in chosen.text
        assert "讲解并提炼这段</button>" in chosen.text
        assert repo.topic_part(user.user_id) is not None


def test_whole_book_selection_clears_pin_and_same_origin_opaque_forms_work(setup):
    _, client, repo, _, user, _, book, calls = setup
    path = "/web/materials/" + book
    fields = Forms(client.get(path + "?part=2").text).values(path + "/study")
    result = client.post(
        path + "/study",
        data=fields,
        headers={"origin": "null", "sec-fetch-site": "same-origin"},
    )
    assert result.status_code == 200
    whole = Forms(client.get(path).text).values(path + "/select")
    assert client.post(path + "/select", data=whole).status_code == 200
    assert repo.topic_part(user.user_id) is None and calls == []


def test_unavailable_pin_is_shown_and_message_does_not_fall_back_to_other_parts(setup):
    _, client, repo, materials, user, _, book, calls = setup
    choose(client, book, 2)
    pin = repo.topic_part(user.user_id)["chunk_id"]
    with sqlite3.connect(materials.database_path) as db:
        db.execute("DELETE FROM material_chunks WHERE chunk_id=?", (pin,))
    page = client.get("/web/welcome")
    assert "原选段暂不可用" in page.text
    fields = Forms(page.text).values("/web/coach/message", "message")
    assert fields["part_id"] == pin
    assert (
        client.post(
            "/web/coach/message", data={**fields, "message": "解释这一段"}
        ).status_code
        == 400
    )
    assert calls == [] and repo.topic_part(user.user_id)["chunk_id"] == pin
