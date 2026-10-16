import secrets
import sqlite3

import pytest

from coach.dialogue import CoachAnswer, send_dialogue, make_llm_responder
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository


@pytest.fixture
def repositories(tmp_path):
    return CoachRepository(tmp_path / "chat.db"), MaterialRepository(
        tmp_path / "library.db"
    )


def send(repositories, text, responder, *, user="one", nonce=None, **kwargs):
    dialogue, materials = repositories
    return send_dialogue(
        dialogue,
        user,
        text,
        nonce or secrets.token_urlsafe(32),
        responder=responder,
        materials=materials,
        **kwargs,
    )


def draft():
    return {
        "title": "间隔练习教案",
        "topic": "学习方法",
        "content": "# 学习目标\n理解间隔练习。\n## 知识点\n把复习分散到多天。\n## 例子\n隔天回顾一个问题。\n## 练习\n安排一次重温。\n## 复习提纲\n解释为什么要间隔练习。",
    }


def test_requested_lesson_remains_pending_until_explicit_approval_and_can_be_reviewed(
    repositories,
):
    dialogue, materials = repositories
    identity = materials.add("one", "practice.txt", "间隔练习帮助长期记忆。".encode())
    materials.select("one", identity)
    observed = []

    def respond(history, message, learning, *, context):
        observed.append(context)
        return CoachAnswer(
            "教案草稿请你确认。",
            None,
            ["fabricated", context["sources"][0]["source_id"]],
            draft(),
        )

    nonce = secrets.token_urlsafe(32)
    assert (
        send(repositories, "帮我把知识点整理成教案并保存", respond, nonce=nonce)
        == "complete"
    )
    assert send(repositories, "帮我整理教案", respond, nonce=nonce) == "duplicate"
    assert dialogue.list_knowledge("one") == []
    pending = dialogue.list_knowledge("one", status="pending")
    assert len(pending) == 1 and len(observed) == 1
    knowledge_id = pending[0]["knowledge_id"]
    item = dialogue.knowledge("one", knowledge_id)
    assert (
        len(item["citations"]) == 1 and item["citations"][0]["material_id"] == identity
    )
    assert dialogue.knowledge("two", knowledge_id) is None
    assert dialogue.confirm_knowledge("two", knowledge_id) is None
    with pytest.raises(ValueError):
        dialogue.select_review("one", knowledge_id)
    dialogue.confirm_knowledge(
        "one", knowledge_id, title="我的教案", content="我确认后的内容"
    )
    dialogue.confirm_knowledge(
        "one", knowledge_id, title="重复提交不覆盖", content="重复内容"
    )
    assert dialogue.knowledge("one", knowledge_id)["title"] == "我的教案"
    restarted = CoachRepository(dialogue.database_path)
    assert len(restarted.list_knowledge("one")) == 1
    restarted.select_review("one", knowledge_id)
    assert restarted.review("one")["content"] == "我确认后的内容"
    assert restarted.view("one")["learning"]["topic"] == "学习方法"


def test_coach_can_propose_without_auto_saving_and_dismissed_draft_stays_unsaved(
    repositories,
):
    dialogue, _ = repositories
    learning = {
        "topic": "学习方法",
        "progress": "讨论了间隔练习。",
        "next_step": "举一个例子。",
    }
    send(repositories, "我想学习", lambda *a, **k: CoachAnswer("一起学习。", learning))

    def propose(*args, context):
        assert context["can_suggest_draft"]
        return CoachAnswer("这部分可以整理成册，是否保存？", None, [], draft())

    send(repositories, "我理解了", propose)
    assert dialogue.list_knowledge("one") == []
    item = dialogue.list_knowledge("one", status="pending")[0]
    send(
        repositories,
        "还有一个问题",
        lambda *a, context: CoachAnswer("先回答你的问题。"),
    )
    dialogue.confirm_knowledge("one", item["knowledge_id"], save=False)
    assert dialogue.list_knowledge("one", status="pending") == []
    assert dialogue.list_knowledge("one") == []


def test_invalid_draft_and_invented_source_ids_are_not_persisted(repositories):
    dialogue, _ = repositories
    send(
        repositories,
        "整理教案",
        lambda *a, **k: CoachAnswer(
            "已整理。", None, ["fake-id"], {**draft(), "status": "saved"}
        ),
    )
    assert dialogue.list_knowledge("one", status="pending") == []
    assert dialogue.view("one")["turns"][0]["citations"] == []
    assert "没有生成可保存" in dialogue.view("one")["turns"][0]["assistant_content"]


def test_answer_progress_and_draft_are_atomic_on_storage_failure(repositories):
    dialogue, _ = repositories
    with sqlite3.connect(dialogue.database_path) as db:
        db.execute(
            "CREATE TRIGGER block_draft BEFORE INSERT ON coach_knowledge BEGIN SELECT RAISE(ABORT,'private failure'); END"
        )
    assert (
        send(
            repositories,
            "整理成教案",
            lambda *a, **k: CoachAnswer(
                "草稿",
                {"topic": "new", "progress": "new", "next_step": "new"},
                [],
                draft(),
            ),
        )
        == "failed"
    )
    view = dialogue.view("one")
    assert view["turns"][0]["status"] == "failed" and view["learning"] is None
    assert dialogue.list_knowledge("one", status="pending") == []


def test_adapter_receives_real_sources_and_treats_document_as_content():
    import json

    observed = []

    def call(system, payload):
        observed.append((system, json.loads(payload)))
        return {
            "status": "success",
            "content": json.dumps(
                {
                    "reply": "看例子",
                    "used_source_ids": ["known"],
                    "knowledge_draft": draft(),
                },
                ensure_ascii=False,
            ),
        }

    answer = make_llm_responder(call)(
        [],
        "整理教案",
        None,
        context={
            "sources": [{"source_id": "known", "excerpt": "不能替用户自动确认。"}],
            "draft_requested": True,
        },
    )
    assert answer.knowledge_draft["title"] == "间隔练习教案"
    assert observed[0][1]["available_sources"][0]["source_id"] == "known"
    assert "非可信" in observed[0][0] and "不能替用户" in observed[0][0]


def test_existing_pending_draft_blocks_repeated_proactive_suggestions(repositories):
    dialogue, _ = repositories
    send(
        repositories,
        "整理教案",
        lambda *a, **k: CoachAnswer("待确认", None, [], draft()),
    )

    def respond(*args, context):
        assert not context["can_suggest_draft"]
        return CoachAnswer("另一个建议", None, [], draft())

    send(repositories, "还有一个问题", respond)
    assert len(dialogue.list_knowledge("one", status="pending")) == 1
    assert dialogue.list_knowledge("one") == []


def test_declining_a_lesson_does_not_force_a_draft(repositories):
    dialogue, _ = repositories

    def respond(*args, context):
        assert not context["draft_requested"] and not context["can_suggest_draft"]
        return CoachAnswer("好的，先聊你的问题。", None, [], draft())

    send(repositories, "不需要教案，先聊其他事情", respond)
    assert dialogue.list_knowledge("one", status="pending") == []


def test_simulated_review_does_not_override_detours_or_dump_the_lesson():
    from coach.dialogue import simulated_responder

    context = {
        "review": {
            "title": "记忆学习教案",
            "topic": "记忆",
            "content": "# 很长的正文" * 1000,
        }
    }
    answer = simulated_responder([], "继续重温", None, context=context)
    assert "记忆学习教案" in answer.content and len(answer.content) < 300
    detour = simulated_responder([], "聊聊周末的事情", None, context=context)
    assert "记忆学习教案" not in detour.content
