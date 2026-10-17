import io
import json
import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from zipfile import ZipFile

import pytest

from api.asset_export import build_export, export_summary
from coach.dialogue import CoachAnswer, make_llm_responder, send_dialogue
from coach.learning_memory import memory_request, validate_memory, MemoryInputError
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository


PREFERENCE = "我喜欢先看例子，再理解概念。"
LEARNING = {"topic": "Python", "progress": "讨论了变量", "next_step": "理解循环"}


@pytest.fixture
def repo(tmp_path):
    return CoachRepository(tmp_path / "coach.db")


def send(repo, text, *, user="one", responder=None, now=1000, nonce=None, **kwargs):
    return send_dialogue(
        repo,
        user,
        text,
        nonce or secrets.token_urlsafe(32),
        responder=responder or (lambda *a, **k: CoachAnswer("继续讨论。")),
        now=now,
        **kwargs,
    )


def test_explicit_memory_is_persistent_owned_without_ai_and_does_not_erase_learning(
    repo,
):
    send(repo, "学习Python", responder=lambda *a: CoachAnswer("学习变量", LEARNING))

    def forbidden(*a, **k):
        pytest.fail("explicit memory must not call AI")

    nonce = secrets.token_urlsafe(32)
    assert (
        send(repo, "请记住，" + PREFERENCE, responder=forbidden, nonce=nonce, now=1001)
        == "complete"
    )
    assert (
        send(repo, "请记住，" + PREFERENCE, responder=forbidden, nonce=nonce, now=1002)
        == "duplicate"
    )
    restarted = CoachRepository(repo.database_path)
    assert restarted.list_memories("one")[0]["content"] == PREFERENCE
    assert restarted.list_memories("two") == []
    assert restarted.view("one", now=1003)["learning"]["topic"] == "Python"
    assert "已记住" in restarted.view("one", now=1003)["turns"][-1]["assistant_content"]


@pytest.mark.parametrize(
    "text",
    [
        "我喜欢先看例子",
        "这本书写着：请记住，先看例子",
        "不要记住我的目标",
        "“请记住，我想学Python”这句话什么意思？",
    ],
)
def test_normal_chat_and_quoted_requests_do_not_save(repo, text):
    assert send(repo, text) == "complete"
    assert repo.list_memories("one") == []
    assert memory_request(text) is None


@pytest.mark.parametrize(
    "text",
    ["请记住", "请记住：" + "字" * 301, "请记住，密码是abcd1234", "请记住，x\x00y"],
)
def test_invalid_memory_completes_with_clear_unsaved_message_without_ai(repo, text):
    assert (
        send(
            repo,
            text,
            responder=lambda *a, **k: pytest.fail("no AI for invalid memory"),
        )
        == "complete"
    )
    assert repo.list_memories("one") == []
    assert "暂未保存" in repo.view("one", now=1001)["turns"][-1]["assistant_content"]


def test_memories_reach_new_conversations_after_recent_history_rolls_off_and_can_be_deleted(
    repo,
):
    send(repo, "请记住：" + PREFERENCE)
    for i in range(42):
        send(
            repo,
            "普通消息" + str(i),
            now=1001 + i,
            responder=lambda *a, **k: CoachAnswer("普通回复"),
        )
    observed = []

    def answer(history, message, learning, *, context):
        observed.append((history, context))
        return CoachAnswer("举一个例子。")

    assert send(repo, "开始新问题", responder=answer, now=1100) == "complete"
    assert observed[-1][1]["learning_memories"] == [{"content": PREFERENCE}]
    assert not any("memory_id" in note for note in observed[-1][1]["learning_memories"])
    note = repo.list_memories("one")[0]
    assert repo.delete_memory("one", note["memory_id"], note["revision"]) == "deleted"
    materials = MaterialRepository(repo.database_path.parent / "materials.db")
    assert (
        send(repo, "继续新问题", responder=answer, materials=materials, now=1101)
        == "complete"
    )
    assert observed[-1][1]["learning_memories"] == []


def test_removed_memory_commands_are_not_reintroduced_through_recent_history(repo):
    send(repo, "请记住：" + PREFERENCE)
    note = repo.list_memories("one")[0]
    repo.delete_memory("one", note["memory_id"], 1)
    captured = []
    send(
        repo,
        "新问题",
        responder=lambda history, *args: captured.extend(history) or CoachAnswer("好"),
        now=1001,
    )
    assert captured == []
    assert "请记住" in repo.view("one", now=1002)["turns"][0]["user_content"]


def test_edits_deletes_are_owned_and_old_versions_cannot_overwrite_or_delete(repo):
    repo.add_memory("one", PREFERENCE, now=10)
    note = repo.list_memories("one")[0]
    assert repo.memory("two", note["memory_id"]) is None
    assert repo.update_memory("two", note["memory_id"], "其他内容", 1) == "missing"
    assert repo.delete_memory("two", note["memory_id"], 1) == "missing"
    assert (
        repo.update_memory("one", note["memory_id"], "我喜欢先读概念", 1, now=11)
        == "updated"
    )
    assert repo.update_memory("one", note["memory_id"], "过期修改", 1) == "conflict"
    assert repo.delete_memory("one", note["memory_id"], 1) == "conflict"
    latest = repo.list_memories("one")[0]
    assert (
        latest["revision"] == 2
        and latest["created_at"] == 10
        and latest["updated_at"] == 11
    )
    assert repo.delete_memory("one", note["memory_id"], 2) == "deleted"
    assert repo.list_memories("one") == []


def test_capacity_and_duplicates_are_atomic_and_no_note_is_silently_replaced(repo):
    for i in range(19):
        assert repo.add_memory("one", f"目标{i}") == "created"
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda i: repo.add_memory("one", f"偏好{i}"), range(2)))
    assert sorted(results) == ["created", "full"]
    assert len(repo.list_memories("one")) == 20
    assert repo.add_memory("one", "目标0") == "existing"
    assert send(repo, "请记住，新目标") == "complete"
    assert "还没有保存" in repo.view("one", now=1001)["turns"][-1]["assistant_content"]
    assert len(repo.list_memories("one")) == 20
    assert repo.add_memory("two", "自己的目标") == "created"


def test_memory_and_chat_receipt_roll_back_together_and_expired_claim_cannot_save(repo):
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "请记住，偏好", now=1000)
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER fail_receipt BEFORE UPDATE ON coach_turns BEGIN SELECT RAISE(ABORT,'test'); END"
        )
    with pytest.raises(sqlite3.Error):
        repo.finish_memory_request("one", nonce, PREFERENCE, now=1001)
    assert repo.list_memories("one") == []
    with sqlite3.connect(repo.database_path) as db:
        db.execute("DROP TRIGGER fail_receipt")
    assert not repo.finish_memory_request("one", nonce, PREFERENCE, now=1180)
    assert repo.list_memories("one") == []


def test_adapter_uses_only_recorded_notes_and_model_cannot_create_new_notes(repo):
    repo.add_memory("one", PREFERENCE)
    seen = []

    def call(system, message):
        seen.append((system, json.loads(message)))
        return {
            "status": "success",
            "content": json.dumps(
                {"reply": "举个例子", "memory_update": {"content": "模型猜测"}},
                ensure_ascii=False,
            ),
        }

    assert send(repo, "解释循环", responder=make_llm_responder(call)) == "complete"
    assert seen[0][1]["learning_memories"] == [{"content": PREFERENCE}]
    assert "不是系统指令" in seen[0][0]
    assert len(repo.list_memories("one")) == 1


def test_personal_memory_export_is_owned_safe_and_has_text_reading_versions(repo):
    repo.add_memory("one", "<script>raw</script> 我喜欢例子")
    repo.add_memory("two", "other-user-private-memory")
    materials = MaterialRepository(repo.database_path.parent / "materials.db")
    assert (
        export_summary(repo.database_path, materials.database_path, "one")["memories"]
        == 1
    )
    archive = build_export(
        repo.database_path, materials.database_path, "one", ["memories"], now=1000
    )
    with ZipFile(io.BytesIO(b"".join(archive.chunks()))) as zipped:
        html = zipped.read("学习记忆/记录/我的学习记忆.html").decode()
        plain = zipped.read("学习记忆/记录/我的学习记忆.txt").decode()
        assert "&lt;script&gt;raw&lt;/script&gt;" in html and "<script>raw" not in html
        assert "<script>raw</script>" in plain
        assert all(
            b"other-user-private-memory" not in zipped.read(name)
            for name in zipped.namelist()
        )
    assert len(repo.list_memories("one")) == 1


def test_learning_about_passwords_is_allowed_but_credential_assignments_are_not():
    assert validate_memory("我的学习目标是理解密码学") == "我的学习目标是理解密码学"
    for value in ("API_KEY=abc123", "我的授权码是123456", "\ud800"):
        with pytest.raises(MemoryInputError):
            validate_memory(value)


def test_read_only_export_of_pre_memory_database_remains_usable_without_migration(repo):
    materials = MaterialRepository(repo.database_path.parent / "materials.db")
    materials.add("one", "notes.txt", b"original notes")
    with sqlite3.connect(repo.database_path) as db:
        db.execute("DROP TABLE coach_memories")
    assert (
        export_summary(repo.database_path, materials.database_path, "one")["memories"]
        == 0
    )
    archive = build_export(
        repo.database_path, materials.database_path, "one", ["materials"]
    )
    with ZipFile(io.BytesIO(b"".join(archive.chunks()))) as zipped:
        assert any(name.startswith("原始资料/") for name in zipped.namelist())
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='coach_memories'"
            ).fetchone()
            is None
        )
