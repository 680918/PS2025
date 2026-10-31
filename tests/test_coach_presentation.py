import secrets

import pytest
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from api.coach_markdown import coach_markdown
from coach.dialogue import CoachAnswer, send_dialogue
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_web_coach_dialogue import login, add_user, form, PASSWORD, BASE


RICH_REPLY = """## 蓝图六问

**任务边界**：写清目的。

| 项目 | 内容 |
| --- | --- |
| 学习 | 从一个问题开始 |

```python
def learn():
    return "每天进步"
```
"""


@pytest.fixture(scope="module")
def user_password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, user_password_hash):
    user = add_user(tmp_path, user_password_hash, "one@example.com", "阅读体验者")
    calls = []

    def responder(*args, **kwargs):
        calls.append(True)
        return CoachAnswer(RICH_REPLY)

    app = create_account_app(tmp_path, dialogue_responder=responder)
    with TestClient(app, base_url=BASE) as client:
        yield app, client, calls, user, responder


def test_markdown_formats_heading_table_and_code_without_remote_or_active_content():
    rendered = coach_markdown(
        RICH_REPLY
        + "\n<script>alert(1)</script>\n![x](https://outside.example/x)\n[x](javascript:alert(1))"
    )
    assert "<h2>蓝图六问</h2>" in rendered
    assert "<strong>任务边界</strong>" in rendered
    assert (
        'class="markdown-table-scroll"' in rendered and '<th scope="col">' in rendered
    )
    assert "<td>从一个问题开始</td>" in rendered
    assert 'class="code-block"' in rendered and "代码 · python" in rendered
    assert "def learn():\n    return" in rendered
    assert (
        "<script>" not in rendered
        and "<img" not in rendered
        and "<a href=" not in rendered
    )
    assert "&lt;script&gt;" in rendered


def test_escaped_formatting_is_fixed_without_changing_code_literals():
    content = (
        r"\## 知识点"
        + "\n\n"
        + r"**边界\*\*"
        + "\n\n```text\n"
        + r"\*\*literal\*\*"
        + "\n```\n\n"
        + r"`\*\*inline\*\*`"
    )
    rendered = coach_markdown(content)
    assert "<h2>知识点</h2>" in rendered and "<strong>边界</strong>" in rendered
    assert r"\*\*literal\*\*" in rendered and r"\*\*inline\*\*" in rendered


def test_first_page_and_older_history_use_the_same_safe_renderer(setup, tmp_path):
    _, client, calls, user, _ = setup
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    for index in range(41):
        nonce = secrets.token_urlsafe(32)
        repo.claim(user.user_id, nonce, "<b>用户原文</b>", now=2000 + index)
        repo.finish(user.user_id, nonce, RICH_REPLY, None, now=2000 + index)
    page = login(client)
    assert "<h2>蓝图六问</h2>" in page.text
    assert (
        "&lt;b&gt;用户原文&lt;/b&gt;" in page.text
        and "<b>用户原文</b>" not in page.text
    )
    cursor = repo.view(user.user_id)["before"]
    older = client.get(f"/web/coach/history?before={cursor}").json()
    assert len(older["turns"]) == 1
    assert older["turns"][0]["assistant_html"] == coach_markdown(RICH_REPLY)
    assert calls == []


def test_pending_drafts_and_greeting_remain_in_left_assets_without_learning_panel(
    setup, tmp_path
):
    _, client, _, user, _ = setup
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    nonce = secrets.token_urlsafe(32)
    repo.claim(user.user_id, nonce, "整理教案", now=2000)
    repo.finish(
        user.user_id,
        nonce,
        "待确认",
        None,
        now=2000,
        draft={"title": "集中的教案", "topic": "知识资产", "content": RICH_REPLY},
    )
    page = login(client).text
    sidebar = page.split('<aside class="workspace-sidebar"', 1)[1].split("</aside>", 1)[
        0
    ]
    assert "欢迎回来" in sidebar and "知识资产沉淀" in sidebar
    assert "教案草稿 · 预览与保存" in sidebar and "待你确认" in sidebar
    assert "已保存的教案目录" in sidebar
    assert "集中的教案" not in page
    assert 'id="workspace-learning"' not in page
    assert "当前学习主题" not in page
    assert repo.list_knowledge(user.user_id) == []


def test_resume_has_specific_natural_introduction_and_preserves_lesson(tmp_path):
    repo = CoachRepository(tmp_path / "conversation.db")
    learning = {
        "topic": "Agent 设计",
        "progress": "已讨论任务边界",
        "next_step": "设计工具",
    }
    assert (
        send_dialogue(
            repo,
            "one",
            "我想学习 Agent 设计",
            secrets.token_urlsafe(32),
            responder=lambda *a: CoachAnswer("先讨论任务边界。", learning),
            now=2000,
        )
        == "complete"
    )
    assert (
        send_dialogue(
            repo,
            "one",
            "",
            secrets.token_urlsafe(32),
            action="continue",
            responder=lambda *a: CoachAnswer("## 先把位置对齐\n\n接着讨论工具的输入。"),
            now=2001,
        )
        == "complete"
    )
    answer = repo.view("one", now=2002)["turns"][-1]["assistant_content"]
    assert answer.startswith("我们回到「Agent 设计」学习主题上来。")
    assert "先把位置对齐" not in answer and "接着讨论工具的输入" in answer
    assert repo.view("one", now=2002)["learning"]["topic"] == "Agent 设计"


def test_knowledge_asset_list_keeps_confirmation_and_saved_catalog_separate(setup):
    _, client, _, _, _ = setup
    login(client)
    page = client.get("/web/knowledge?status=pending")
    assert "知识资产沉淀" in page.text
    assert "教案草稿 · 预览与保存" in page.text and "已保存的教案目录" in page.text
    assert "<script>" not in page.text


def test_waiting_submission_uses_same_csrf_nonce_and_never_retries(setup):
    _, client, calls, _, _ = setup
    login(client)
    values = form(client)
    headers = {"Accept": "application/json"}
    response = client.post("/web/coach/message", data=values, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"redirect": "/web/welcome#coach-dialog"}
    assert (
        client.post("/web/coach/message", data=values, headers=headers).status_code
        == 200
    )
    assert len(calls) == 1
    invalid = client.post(
        "/web/coach/message", data={**form(client), "csrf": "a" * 64}, headers=headers
    )
    assert invalid.status_code == 403 and len(calls) == 1
