import json
import secrets
import sqlite3
from uuid import uuid4
from zipfile import ZipFile

import pytest

from api.asset_export import build_export
from coach.dialogue import CoachAnswer, make_llm_responder, send_dialogue
from coach.materials import MaterialRepository
from coach.unit_lessons import unit_lesson_plan, send_unit_lesson
from conversation.coach_repository import CoachRepository


@pytest.fixture
def setup(tmp_path):
    materials = MaterialRepository(tmp_path / "materials.db")
    book = materials.add("one", "a.txt", ("甲" * 7200).encode(), title="<读书资料>")
    repo = CoachRepository(tmp_path / "coach.db", materials=materials)
    unit = uuid4().hex
    repo.save_book_unit("one", book, unit, "第一单元", 1, 9, 0, now=1000)
    chunks = materials.chunks("one", book)
    for part in chunks[:8]:
        nonce = secrets.token_urlsafe(32)
        repo.claim("one", nonce, "已讲解", now=1000)
        repo.finish(
            "one",
            nonce,
            "本段讲解",
            None,
            now=1001,
            material_id=book,
            part_id=part["chunk_id"],
            explained_part=True,
        )
    return repo, materials, book, unit, chunks


def answer(history, message, learning, *, context):
    return CoachAnswer(
        "草稿已生成",
        {"topic": "不得修改", "progress": "不得写入", "next_step": "不得写入"},
        [row["source_id"] for row in context["sources"]],
        {
            "title": "单元复习教案",
            "topic": "错误主题",
            "content": "## 核心知识\n结合例子重温。",
        },
    )


def send(setup, *, responder=answer, batch=1, nonce=None, now=1002):
    repo, materials, book, unit, _ = setup
    plan = unit_lesson_plan(repo, materials, "one", book, unit)
    return send_unit_lesson(
        repo,
        materials,
        "one",
        book,
        unit,
        batch,
        plan["batches"][batch - 1]["digest"],
        nonce or secrets.token_urlsafe(32),
        responder=responder,
        now=now,
    )


def test_batches_only_explained_sources_and_preserve_active_learning(setup):
    repo, materials, book, unit, chunks = setup
    active = repo.create_topic("one", "Python", now=1000)
    before = repo.active_topic("one")
    seen = []

    def respond(history, message, learning, *, context):
        seen.append(context)
        assert history == [] and learning is None
        assert len(context["sources"]) == 6 and context["selected_part"] is None
        return answer(history, message, learning, context=context)

    assert send(setup, responder=respond) == "complete"
    assert repo.active_topic("one") == before
    assert repo.topic_turns("one", active) == []
    pending = repo.list_knowledge("one", status="pending")
    assert len(pending) == 1 and repo.list_knowledge("one") == []
    item = repo.knowledge("one", pending[0]["knowledge_id"])
    scope = item["unit_summary"]
    assert scope["batch_count"] == 2 and scope["explained"] == 8 and scope["total"] == 9
    assert [row["chunk_id"] for row in scope["sources"]] == [
        row["chunk_id"] for row in chunks[:6]
    ]
    assert len(item["citations"]) == 6
    assert len(repo.book_coverage("one", book)) == 8
    assert send(setup, batch=2, now=1003) == "complete"
    item = repo.knowledge(
        "one", repo.list_knowledge("one", status="pending")[0]["knowledge_id"]
    )
    assert item["unit_summary"]["batch"] == 2 and len(item["citations"]) == 2
    assert all(row["source_id"] != chunks[8]["chunk_id"] for row in item["citations"])


@pytest.mark.parametrize("kind", ["missing", "partial", "invalid", "exception", "late"])
def test_invalid_or_late_output_never_creates_knowledge(setup, kind):
    repo, _, book, unit, _ = setup

    def respond(history, message, learning, *, context):
        if kind == "exception":
            raise RuntimeError("private provider body must not be saved")
        if kind == "late":
            repo.view("one", now=1300)
        result = answer(history, message, learning, context=context)
        if kind == "invalid":
            return {"knowledge_draft": "forged"}
        if kind in {"missing", "partial"}:
            return CoachAnswer(
                result.content,
                used_source_ids=[] if kind == "missing" else result.used_source_ids[:1],
                knowledge_draft=result.knowledge_draft,
            )
        return result

    assert send(setup, responder=respond) in {"complete", "failed", "interrupted"}
    assert repo.unit_knowledge("one", book, unit) == []
    assert "private provider body" not in str(repo.view("one", now=1301))


def test_replay_and_stale_scope_do_not_call_model(setup):
    repo, materials, book, unit, chunks = setup
    nonce = secrets.token_urlsafe(32)
    calls = []

    def respond(*a, **k):
        calls.append(1)
        return answer(*a, **k)

    assert send(setup, responder=respond, nonce=nonce) == "complete"
    assert send(setup, responder=respond, nonce=nonce) == "duplicate"
    assert calls == [1]
    plan = unit_lesson_plan(repo, materials, "one", book, unit)
    repo.save_book_unit("one", book, unit, "改名", 1, 9, 1, now=1003)
    with pytest.raises(ValueError, match="变化"):
        send_unit_lesson(
            repo,
            materials,
            "one",
            book,
            unit,
            1,
            plan["batches"][0]["digest"],
            secrets.token_urlsafe(32),
            responder=respond,
            now=1004,
        )
    assert calls == [1]
    assert repo.unit_knowledge("other", book, unit) == []
    with pytest.raises(ValueError):
        unit_lesson_plan(repo, materials, "other", book, unit)


def test_claim_rechecks_scope_and_coverage_in_transaction(setup):
    repo, materials, book, unit, _ = setup
    old = unit_lesson_plan(repo, materials, "one", book, unit)
    repo.save_book_unit("one", book, unit, "新版本", 1, 9, 1, now=1002)
    with pytest.raises(ValueError, match="变化"):
        repo.claim(
            "one",
            secrets.token_urlsafe(32),
            "stale",
            now=1003,
            unit_guard=old["guard"],
            detached=True,
        )
    current = unit_lesson_plan(repo, materials, "one", book, unit)
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "DELETE FROM coach_book_coverage WHERE chunk_id=?",
            (current["guard"]["coverage_ids"][0],),
        )
    with pytest.raises(ValueError, match="变化"):
        repo.claim(
            "one",
            secrets.token_urlsafe(32),
            "stale",
            now=1003,
            unit_guard=current["guard"],
            detached=True,
        )


def test_link_failure_rolls_back_draft_and_response(setup):
    repo, _, book, unit, _ = setup
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER fail_link BEFORE INSERT ON coach_knowledge_units BEGIN SELECT RAISE(ABORT,'test'); END"
        )
    assert send(setup) == "failed"
    assert (
        repo.unit_knowledge("one", book, unit) == []
        and repo.list_knowledge("one", status="pending") == []
    )
    assert repo.view("one", now=1003)["turns"][-1]["status"] == "failed"


def test_saved_unit_lesson_scope_survives_revision_review_and_export(setup):
    repo, materials, book, unit, _ = setup
    assert send(setup) == "complete"
    item = repo.unit_knowledge("one", book, unit)[0]
    identity = item["knowledge_id"]
    repo.confirm_knowledge("one", identity)
    repo.revise_knowledge(
        "one",
        identity,
        1,
        title="最新复习教案",
        content="这是用户修订后的正文。",
        now=1004,
    )
    repo.save_book_unit("one", book, unit, "新单元名称", 2, 9, 1, now=1005)
    saved = repo.knowledge("one", identity)
    assert saved["unit_summary"]["unit_title"] == "第一单元"
    repo.select_review("one", identity, material_id=book)
    contexts = []

    def review(*a, context, **k):
        contexts.append(context)
        return CoachAnswer("重温当前教案")

    assert (
        send_dialogue(
            repo,
            "one",
            "重温这份教案",
            secrets.token_urlsafe(32),
            responder=review,
            materials=materials,
            now=1006,
        )
        == "complete"
    )
    assert contexts[0]["review"]["content"] == "这是用户修订后的正文。"
    assert contexts[0]["review"]["unit_summary"]["unit_title"] == "第一单元"
    archive = build_export(
        repo.database_path, materials.database_path, "one", ["saved"]
    )
    try:
        with ZipFile(archive.file) as bundle:
            md = next(name for name in bundle.namelist() if name.endswith(".md"))
            text = bundle.read(md).decode()
            assert (
                "第一单元" in text
                and "第 1 / 2 批" in text
                and "这是用户修订后的正文。" in text
            )
    finally:
        archive.close()


def test_model_adapter_receives_scope_as_data(setup):
    payloads = []

    def call(system, payload):
        data = json.loads(payload)
        payloads.append(data)
        assert "unit_lesson" in data and "unit_lesson 非空" in system
        return {
            "status": "success",
            "content": json.dumps(
                {
                    "reply": "草稿",
                    "learning_update": None,
                    "used_source_ids": [
                        row["source_id"] for row in data["available_sources"]
                    ],
                    "knowledge_draft": {
                        "title": "复习",
                        "topic": "单元",
                        "content": "可重温正文",
                    },
                }
            ),
        }

    assert send(setup, responder=make_llm_responder(call)) == "complete"
    assert len(payloads[0]["available_sources"]) == 6
