"""Exercise the account-based product journey with an entirely simulated coach."""

import copy
import smtplib

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from api.account_pages import SESSION_COOKIE
from coach.dialogue import CoachAnswer
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_coach_materials import pdf_bytes
from tests.test_web_coach_dialogue import BASE, PASSWORD, Forms, add_user, form, login
from tests.test_web_knowledge_search import Links


@pytest.fixture(autouse=True)
def no_real_mail_or_model(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("No real AI or email in the integrated product journey")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


def database_bytes(repo, materials):
    return {
        path: path.read_bytes()
        for path in (repo.database_path, materials.database_path)
    }


def learning_position(repo, user_id):
    selected = repo.topic_part(user_id)
    # A request can refresh its timestamp while the actual book/part stays put.
    return {
        key: selected[key] for key in ("user_id", "topic_id", "material_id", "chunk_id")
    }


@pytest.mark.parametrize("kind", ["txt", "pdf"])
def test_owned_book_detour_lesson_revision_sources_export_review_and_restart(
    tmp_path,
    password_hash,
    kind,
):
    user = add_user(tmp_path, password_hash, "one@example.com", "全流程体验者")
    add_user(tmp_path, password_hash, "two@example.com", "另一位体验者")
    calls = []

    def respond(history, message, learning, *, context):
        calls.append(copy.deepcopy(context))
        if message == "今天有点累，先聊聊如何休息":
            return CoachAnswer("可以先休息一下，稍后再接着讨论。", None)
        reviewing = context.get("review") is not None
        update = (
            None
            if reviewing
            else dict(
                topic=learning["topic"],
                progress="已讨论所选片段与具体例子",
                next_step="用自己的话解释并核对遗漏",
            )
        )
        return CoachAnswer(
            "## 从一个例子开始\n\n先尝试解释，再核对资料。",
            update,
            [source["source_id"] for source in context["sources"]],
            dict(
                title="回想与核对教案",
                topic=learning["topic"],
                content="## 学习目标\n先回想，再核对。\n\n| 方法 | 用途 |\n| --- | --- |\n| 回想 | 找出遗漏 |",
            )
            if context["draft_requested"]
            else None,
        )

    app = create_account_app(
        tmp_path, dialogue_responder=respond, dialogue_label="模拟验收"
    )
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    materials = MaterialRepository(tmp_path / "coach_library.db")
    message_path = "/web/coach/message"
    original_title = "验收资料（回答时书名）"
    original_raw = (
        pdf_bytes() if kind == "pdf" else ("回想和核对的虚构资料。\n" * 190).encode()
    )
    revised_content = "## 已修订教案\n\n先合上资料复述，再核对遗漏。\n\n~~~python\nif reviewing:\n    recall_then_check()\n~~~"

    with TestClient(app, base_url=BASE) as client:
        assert login(client).status_code == 200
        upload = Forms(client.get("/web/materials").text).values(
            "/web/materials/upload"
        )
        preview = client.post(
            "/web/materials/upload",
            data={"csrf": upload["csrf"], "title": original_title},
            files={"file": ("trial." + kind, original_raw, "application/octet-stream")},
        )
        assert preview.status_code == 200 and calls == []
        book = materials.list(user.user_id)[0]["material_id"]
        chunks = materials.chunks(user.user_id, book)
        index = 1 if kind == "pdf" else 2
        chunk = chunks[index - 1]
        material_path = "/web/materials/" + book
        pick = Forms(client.get(material_path + f"?part={index}").text).values(
            material_path + "/study"
        )
        workspace = client.post(material_path + "/study", data=pick)
        assert workspace.status_code == 200 and calls == []
        first_fields = Forms(workspace.text).values(message_path, "study")
        first = client.post(message_path, data=first_fields)
        assert first.status_code == 200 and len(calls) == 1
        assert (
            len(calls[0]["sources"]) == 1
            and calls[0]["sources"][0]["source_id"] == chunk["chunk_id"]
        )
        topic_before = repo.active_topic(user.user_id)
        part_before = learning_position(repo, user.user_id)
        assert part_before["chunk_id"] == chunk["chunk_id"]
        # Replaying the original submission cannot create a second paid request.
        assert (
            client.post(message_path, data=first_fields).status_code == 200
            and len(calls) == 1
        )
        detour = client.post(
            message_path, data={**form(client), "message": "今天有点累，先聊聊如何休息"}
        )
        assert detour.status_code == 200 and len(calls) == 2
        assert (
            repo.active_topic(user.user_id) == topic_before
            and learning_position(repo, user.user_id) == part_before
        )
        resumed = client.post(message_path, data=form(client, "continue"))
        assert resumed.status_code == 200 and len(calls) == 3
        assert calls[-1]["selected_part"]["chunk_index"] == index
        draft_reply = client.post(message_path, data=form(client, "lesson"))
        assert draft_reply.status_code == 200 and len(calls) == 4
        assert repo.list_knowledge(user.user_id) == []
        draft = repo.list_knowledge(user.user_id, status="pending")[0]
        identity = draft["knowledge_id"]
        draft = repo.knowledge(user.user_id, identity)
        lesson_path = "/web/knowledge/" + identity
        saved_fields = Forms(client.get(lesson_path).text).values(lesson_path + "/save")
        saved_values = {
            **saved_fields,
            "title": "我的回想教案",
            "content": draft["content"],
        }
        unchanged = database_bytes(repo, materials)
        checked = client.post(
            f"/web/lesson-preview/{identity}/draft", data=saved_values
        )
        assert checked.status_code == 200 and "<table>" in checked.text
        assert database_bytes(repo, materials) == unchanged and len(calls) == 4
        saved = client.post(lesson_path + "/save", data=saved_values)
        assert (
            saved.status_code == 200
            and repo.knowledge(user.user_id, identity)["status"] == "saved"
        )
        edit = Forms(client.get(lesson_path + "/edit").text).values(
            lesson_path + "/revise"
        )
        revision_values = {
            **edit,
            "title": "我的回想教案（第2版）",
            "content": revised_content,
        }
        unchanged = database_bytes(repo, materials)
        checked = client.post(
            f"/web/lesson-preview/{identity}/saved", data=revision_values
        )
        assert checked.status_code == 200 and "    recall_then_check()" in checked.text
        assert database_bytes(repo, materials) == unchanged
        revised = client.post(lesson_path + "/revise", data=revision_values)
        assert (
            revised.status_code == 200
            and repo.knowledge(user.user_id, identity)["revision"] == 2
        )
        rename = Forms(client.get(material_path + "/edit").text).values(
            material_path + "/edit"
        )
        assert (
            client.post(
                material_path + "/edit", data={**rename, "title": "验收资料（改名后）"}
            ).status_code
            == 200
        )

        # New read-only surfaces must agree about the same origin, source, and version.
        unchanged = database_bytes(repo, materials)
        compared = client.get(lesson_path + "/compare?base=1&target=2")
        assert compared.status_code == 200 and "正文新增" in compared.text
        assert (
            "已修订教案" in compared.text and "    recall_then_check()" in compared.text
        )
        source = client.get(lesson_path + "/sources/1")
        assert (
            source.status_code == 200
            and original_title in source.text
            and "验收资料（改名后）" in source.text
        )
        assert (
            chunk["content"] in source.text
            and source.headers["cache-control"] == "no-store"
        )
        item = repo.knowledge(user.user_id, identity)
        assert item["citations"][0]["source_id"] == chunk["chunk_id"]
        origin_path = "/web/conversations/" + str(item["turn_id"])
        origin = client.get(origin_path)
        assert origin.status_code == 200 and lesson_path in Links(origin.text).links
        dialogue_source = client.get(origin_path + "/sources/1")
        assert (
            dialogue_source.status_code == 200
            and original_title in dialogue_source.text
        )
        assert (
            f"{origin_path}?q=&amp;topic=&amp;page=1#dialogue-source-1"
            in dialogue_source.text
        )
        readable = client.get(lesson_path + "/readable")
        assert readable.status_code == 200 and "我的回想教案（第2版）" in readable.text
        assert "第 2 版" in readable.text and "    recall_then_check()" in readable.text
        assert client.get(lesson_path + "/download").text == revised_content
        original = client.get(material_path + "/original")
        assert original.status_code == 200 and original.content == original_raw
        assert database_bytes(repo, materials) == unchanged and len(calls) == 4

        saved_now = client.get(lesson_path)
        before_review = repo.active_topic(user.user_id)
        reviewed = client.post(
            lesson_path + "/review",
            data=Forms(saved_now.text).values(lesson_path + "/review"),
        )
        assert (
            reviewed.status_code == 200
            and "正在重温教案" in reviewed.text
            and len(calls) == 4
        )
        review_answer = client.post(
            message_path, data={**form(client), "message": "请用一个例子重温这份教案"}
        )
        assert review_answer.status_code == 200 and len(calls) == 5
        assert (
            calls[-1]["review"]["content"] == revised_content
            and calls[-1]["draft_requested"] is False
        )
        assert (
            repo.active_topic(user.user_id) == before_review
            and learning_position(repo, user.user_id) == part_before
        )
        end_fields = Forms(client.get("/web/welcome").text).values("/web/review/end")
        assert client.post("/web/review/end", data=end_fields).status_code == 200
        assert (
            repo.review(user.user_id) is None
            and repo.active_topic(user.user_id) == before_review
        )
        assert (
            learning_position(repo, user.user_id) == part_before
            and repo.ai_usage(user.user_id)["used"] == 5
        )
        old_revision_fields = revision_values
        token = client.cookies.get(SESSION_COOKIE)

    restarted = create_account_app(tmp_path, dialogue_responder=respond)
    with TestClient(restarted, base_url=BASE) as fresh:
        fresh.cookies.set(SESSION_COOKIE, token)
        workspace = fresh.get("/web/welcome")
        assert workspace.status_code == 200 and "验收资料（改名后）" in workspace.text
        assert repo.active_topic(user.user_id)["topic_id"] == topic_before["topic_id"]
        assert learning_position(repo, user.user_id) == part_before
        assert fresh.get(lesson_path + "/download").text == revised_content
        assert fresh.get(lesson_path + "/sources/1").status_code == 200
        # An editor from the prior process cannot submit after CSRF keys rotate.
        assert (
            fresh.post(lesson_path + "/revise", data=old_revision_fields).status_code
            == 403
        )
        assert (
            repo.knowledge(user.user_id, identity)["revision"] == 2 and len(calls) == 5
        )
        logout = Forms(fresh.get("/web/welcome").text).values("/web/auth/logout")
        fresh.post("/web/auth/logout", data=logout)
        assert fresh.get(lesson_path, follow_redirects=False).status_code == 303

    with TestClient(restarted, base_url=BASE) as other:
        assert login(other, "two@example.com").status_code == 200
        unchanged = database_bytes(repo, materials)
        for path in (
            lesson_path,
            lesson_path + "/sources/1",
            lesson_path + "/compare?base=1&target=2",
            lesson_path + "/readable",
            material_path + "/original",
            origin_path,
            origin_path + "/sources/1",
        ):
            assert other.get(path).status_code == 404, path
        assert repo.list_knowledge(user.user_id, status="pending") == []
        assert database_bytes(repo, materials) == unchanged and len(calls) == 5
