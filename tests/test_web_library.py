import secrets
import smtplib

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from coach.dialogue import CoachAnswer
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_web_coach_dialogue import add_user, login, form, Forms, PASSWORD, BASE
from tests.test_coach_materials import pdf_bytes


@pytest.fixture(autouse=True)
def no_real_services(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("no real SMTP or AI in library tests")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "知识积累者")
    calls = []

    def responder(history, message, learning, *, context):
        calls.append(context)
        return CoachAnswer(
            "请查看实际引用和待确认教案。",
            None,
            [item["source_id"] for item in context["sources"]],
            {
                "title": "复习方法教案",
                "topic": "复习方法",
                "content": "# 学习目标\n理解间隔练习。\n## 例子\n隔天重温一次。",
            }
            if context["draft_requested"]
            else None,
        )

    app = create_account_app(
        tmp_path, dialogue_responder=responder, dialogue_label="模拟 AI"
    )
    with TestClient(app, base_url=BASE) as client:
        yield app, client, user, calls, tmp_path


def upload(client, *, filename="book.txt", raw="间隔练习帮助长期记忆。".encode()):
    csrf = Forms(client.get("/web/materials").text).values("/web/materials/upload")[
        "csrf"
    ]
    return client.post(
        "/web/materials/upload",
        data={"csrf": csrf, "title": "学习资料"},
        files={"file": (filename, raw, "application/octet-stream")},
    )


def test_upload_select_discuss_draft_confirm_export_and_review(setup):
    _, client, user, calls, directory = setup
    login(client)
    preview = upload(client)
    assert preview.status_code == 200 and "间隔练习" in preview.text
    materials = MaterialRepository(directory / "coach_library.db")
    identity = materials.list(user.user_id)[0]["material_id"]
    path = f"/web/materials/{identity}/select"
    selected = client.post(path, data=Forms(preview.text).values(path))
    assert "学习资料" in selected.text
    response = client.post(
        "/web/coach/message", data={**form(client), "message": "把这个知识点整理成教案"}
    )
    assert "引用依据" in response.text and "待你确认" in response.text
    repo = CoachRepository(directory / "coach_conversations.db")
    assert repo.list_knowledge(user.user_id) == []
    knowledge_id = repo.list_knowledge(user.user_id, status="pending")[0][
        "knowledge_id"
    ]
    path = f"/web/knowledge/{knowledge_id}"
    draft = client.get(path)
    fields = Forms(draft.text).values(path + "/save")
    saved = client.post(
        path + "/save",
        data={**fields, "title": "我的复习教案", "content": "已核对的教案正文。"},
    )
    assert "已由你确认保存" in saved.text and "已核对的教案正文" in saved.text
    assert client.get(path + "/download").text == "已核对的教案正文。"
    assert "attachment" in client.get(path + "/download").headers["content-disposition"]
    reviewed = client.post(
        path + "/review", data=Forms(saved.text).values(path + "/review")
    )
    assert "正在重温教案" in reviewed.text and "我的复习教案" in reviewed.text
    assert calls[0]["sources"][0]["excerpt"] in draft.text
    assert "我的复习教案" in client.get("/web/knowledge?q=复习").text


def test_upload_from_conversation_auto_selects_markdown_for_that_chat(setup):
    _, client, user, calls, directory = setup
    login(client)
    start = Forms(client.get("/web/welcome").text).values(
        "/web/coach/conversations/new"
    )
    assert client.post("/web/coach/conversations/new", data=start).status_code == 200
    page = client.get("/web/welcome")
    assert 'href="/web/materials?from=conversation#add-material"' in page.text
    library = client.get("/web/materials?from=conversation")
    upload_form = Forms(library.text).values("/web/materials/upload?from=conversation")
    uploaded = client.post(
        "/web/materials/upload?from=conversation",
        data={"csrf": upload_form["csrf"], "title": "AI Agent 架构设计学习手册"},
        files={
            "file": (
                "AI Agent 架构设计学习手册.md",
                "# 工具边界\n\n工具权限需要人工确认。".encode(),
                "text/markdown",
            )
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.url.path == "/web/welcome"
    selected = MaterialRepository(directory / "coach_library.db").selected(user.user_id)
    assert selected["title"] == "AI Agent 架构设计学习手册"
    response = client.post(
        "/web/coach/message",
        data={**form(client), "message": "今天学习这份手册"},
    )
    assert response.status_code == 200
    assert calls[-1]["sources"]
    assert calls[-1]["sources"][0]["excerpt"] == "# 工具边界\n\n工具权限需要人工确认。"


def test_paste_and_pdf_are_persistent_without_ai_calls(setup):
    _, client, user, calls, directory = setup
    login(client)
    fields = Forms(client.get("/web/materials").text).values("/web/materials/paste")
    response = client.post(
        "/web/materials/paste",
        data={
            **fields,
            "title": "粘贴资料",
            "content": "<script>不能执行</script>这段文字作为资料保存。",
        },
    )
    assert "&lt;script&gt;" in response.text and "<script>" not in response.text
    assert upload(client, filename="real.pdf", raw=pdf_bytes()).status_code == 200
    assert calls == []
    restarted = MaterialRepository(directory / "coach_library.db")
    assert len(restarted.list(user.user_id)) == 2


def test_private_documents_and_lessons_cannot_be_read_by_other_accounts(
    setup, password_hash
):
    app, client, user, _, directory = setup
    login(client)
    upload(client)
    identity = MaterialRepository(directory / "coach_library.db").list(user.user_id)[0][
        "material_id"
    ]
    repo = CoachRepository(directory / "coach_conversations.db")
    nonce = secrets.token_urlsafe(32)
    repo.claim(user.user_id, nonce, "学习", now=1000)
    repo.finish(
        user.user_id,
        nonce,
        "草稿",
        None,
        now=1000,
        draft={"title": "私有教案", "topic": "私有主题", "content": "私有内容"},
    )
    knowledge_id = repo.list_knowledge(user.user_id, status="pending")[0][
        "knowledge_id"
    ]
    add_user(directory, password_hash, "two@example.com", "另一位")
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        assert other.get("/web/materials/" + identity).status_code == 404
        assert other.get("/web/knowledge/" + knowledge_id).status_code == 404
        assert (
            other.get("/web/knowledge/" + knowledge_id + "/download").status_code == 404
        )
        assert "私有教案" not in other.get("/web/knowledge?status=pending").text


def test_missing_login_csrf_bad_origin_and_unsupported_upload_are_rejected(setup):
    _, client, _, calls, _ = setup
    assert client.get("/web/materials", follow_redirects=False).status_code == 303
    assert client.post("/web/materials/paste", data={}).status_code == 200
    login(client)
    assert (
        client.post(
            "/web/materials/paste", data={"csrf": "bad", "title": "x", "content": "x"}
        ).status_code
        == 403
    )
    fields = Forms(client.get("/web/materials").text).values("/web/materials/paste")
    assert (
        client.post(
            "/web/materials/paste",
            data={**fields, "title": "x", "content": "x"},
            headers={"origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert upload(client, filename="x.exe", raw=b"binary").status_code == 400
    assert calls == []


def test_confirm_requires_csrf_and_post_and_does_not_allow_foreign_fields(setup):
    _, client, user, _, directory = setup
    login(client)
    client.post("/web/coach/message", data={**form(client), "message": "整理教案"})
    repo = CoachRepository(directory / "coach_conversations.db")
    identity = repo.list_knowledge(user.user_id, status="pending")[0]["knowledge_id"]
    path = f"/web/knowledge/{identity}"
    assert client.get(path + "/save").status_code == 405
    assert (
        client.post(
            path + "/save", data={"csrf": "bad", "title": "x", "content": "x"}
        ).status_code
        == 403
    )
    fields = Forms(client.get(path).text).values(path + "/save")
    assert (
        client.post(
            path + "/save",
            data={**fields, "title": "x", "content": "x", "user_id": "other"},
        ).status_code
        == 403
    )
    assert repo.list_knowledge(user.user_id) == []


def test_upload_size_and_csrf_boundaries_and_safe_markdown(setup):
    from api.library_pages import lesson_html

    _, client, user, calls, directory = setup
    login(client)
    response = client.post(
        "/web/materials/upload",
        data={"csrf": "bad", "title": "x"},
        files={"file": ("x.txt", b"private")},
    )
    assert response.status_code == 403
    assert upload(client, raw=b"x" * (10 * 1024**2 + 1)).status_code == 400
    assert MaterialRepository(directory / "coach_library.db").list(user.user_id) == []
    rendered = lesson_html(
        "<script>alert(1)</script>\n![x](https://outside.example/a)\n<https://outside.example/>"
    )
    assert (
        "<script>" not in rendered
        and "<img" not in rendered
        and "<a href=" not in rendered
    )
    assert calls == []
