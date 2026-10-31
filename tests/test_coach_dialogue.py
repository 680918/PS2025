import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from coach.dialogue import (
    CoachAnswer,
    make_llm_responder,
    send_dialogue,
    simulated_responder,
)
from conversation.coach_repository import CoachRepository


LEARNING = {
    "topic": "批判性思维",
    "progress": "讨论了证据与观点的区别。",
    "next_step": "比较一组实际例子。",
}


@pytest.fixture
def repo(tmp_path):
    return CoachRepository(tmp_path / "coach.db")


def send(
    repo, text="我想学习批判性思维", *, user="one", responder=None, nonce=None, **kwargs
):
    return send_dialogue(
        repo,
        user,
        text,
        nonce or secrets.token_urlsafe(32),
        responder=responder or (lambda *args: CoachAnswer("从证据开始。", LEARNING)),
        **kwargs,
    )


def test_learning_and_messages_survive_restart_and_are_owned_by_account(repo):
    assert send(repo, now=1000) == "complete"
    restarted = CoachRepository(repo.database_path)
    assert restarted.view("one", now=1001)["learning"] == {
        **LEARNING,
        "updated_at": 1000,
    }
    assert (
        restarted.view("one", now=1001)["turns"][0]["assistant_content"]
        == "从证据开始。"
    )
    assert restarted.view("two", now=1001) == {
        "turns": [],
        "learning": None,
        "before": None,
    }


def test_detour_preserves_learning_and_continue_has_same_history(repo):
    send(repo, now=1000)
    send(
        repo, "今天有点累", responder=lambda *a: CoachAnswer("休息一下也好。"), now=1001
    )
    observed = []

    def resume(history, message, learning):
        observed.append((history, message, learning))
        return CoachAnswer(
            "来看这个例子。", {**LEARNING, "progress": "讨论了证据，并开始比较例子。"}
        )

    assert send(repo, "", responder=resume, action="continue", now=1002) == "complete"
    history, message, learning = observed[0]
    assert len(history) == 4 and history[-2]["content"] == "今天有点累"
    assert message == "继续上次学习：批判性思维"
    assert learning["next_step"] == LEARNING["next_step"]
    assert len(repo.view("one", now=1003)["turns"]) == 3


def test_duplicate_nonce_never_calls_provider_twice_even_after_restart(repo):
    calls, nonce = [], secrets.token_urlsafe(32)

    def responder(*args):
        calls.append(True)
        return CoachAnswer("回复")

    assert send(repo, nonce=nonce, responder=responder, now=1000) == "complete"
    assert (
        send(
            CoachRepository(repo.database_path),
            nonce=nonce,
            responder=responder,
            now=1001,
        )
        == "duplicate"
    )
    assert calls == [True]
    assert (
        send(repo, user="two", nonce=nonce, responder=responder, now=1001) == "complete"
    )
    assert len(calls) == 2


def test_provider_failure_is_saved_without_private_error_and_not_retried(repo):
    nonce, calls = secrets.token_urlsafe(32), []

    def broken(*args):
        calls.append(True)
        raise RuntimeError("private-api-key and private request")

    assert send(repo, nonce=nonce, responder=broken, now=1000) == "failed"
    assert send(repo, nonce=nonce, responder=broken, now=1001) == "duplicate"
    view = repo.view("one", now=1002)
    assert view["turns"][0]["status"] == "failed"
    assert "private" not in str(view)
    assert calls == [True]
    assert send(repo, now=1002) == "complete"


def test_concurrent_messages_for_one_account_are_serialized(repo):
    entered, release = Event(), Event()

    def blocked(*args):
        entered.set()
        assert release.wait(10)
        return CoachAnswer("完成")

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(send, repo, responder=blocked, now=1000)
        try:
            assert entered.wait(10)
            assert send(repo, now=1001) == "busy"
            assert send(repo, user="two", now=1001) == "complete"
        finally:
            release.set()
        assert first.result(timeout=10) == "complete"


def test_interrupted_request_expires_without_resend_and_late_reply_cannot_replace_learning(
    repo,
):
    nonce = secrets.token_urlsafe(32)
    assert repo.claim("one", nonce, "旧消息", now=1000) == "claimed"
    assert repo.view("one", now=1179)["turns"][0]["status"] == "pending"
    assert repo.view("one", now=1180)["turns"][0]["status"] == "failed"
    assert send(repo, now=1181) == "complete"
    assert not repo.finish(
        "one", nonce, "迟到回复", {**LEARNING, "topic": "错误主题"}, now=1182
    )
    assert repo.view("one", now=1183)["learning"]["topic"] == LEARNING["topic"]


@pytest.mark.parametrize(
    "update",
    [
        {"topic": "错误"},
        {**LEARNING, "topic": "x" * 121},
        {**LEARNING, "sources": ["伪造书籍"]},
        {**LEARNING, "progress": ""},
    ],
)
def test_invalid_metadata_does_not_erase_valid_learning(repo, update):
    send(repo, now=1000)
    assert (
        send(repo, responder=lambda *a: CoachAnswer("可以聊聊。", update), now=1001)
        == "complete"
    )
    assert repo.view("one", now=1002)["learning"]["topic"] == LEARNING["topic"]


@pytest.mark.parametrize("answer", [None, CoachAnswer(""), CoachAnswer("x" * 12001)])
def test_invalid_reply_becomes_failed_turn(repo, answer):
    assert send(repo, responder=lambda *args: answer, now=1000) == "failed"
    assert repo.view("one", now=1001)["learning"] is None


@pytest.mark.parametrize("text", ["", "  ", "x" * 2001, None])
def test_invalid_message_never_reaches_provider(repo, text):
    with pytest.raises(ValueError):
        send(repo, text, responder=lambda *a: pytest.fail("must not call"))
    assert repo.view("one")["turns"] == []


def test_resume_needs_existing_anchor_and_does_not_create_message(repo):
    with pytest.raises(ValueError):
        send(
            repo,
            "",
            action="continue",
            responder=lambda *a: pytest.fail("must not call"),
        )
    assert repo.view("one")["turns"] == []


def test_history_is_bounded_and_excludes_failed_turns(repo):
    for i in range(16):
        send(
            repo,
            str(i) * 1000,
            responder=lambda *a: CoachAnswer("a" * 1000),
            now=1000 + i,
        )
    send(repo, "失败的消息", responder=lambda *a: None, now=1020)
    observed = []
    send(
        repo,
        "继续聊",
        responder=lambda history, *a: observed.extend(history) or CoachAnswer("好"),
        now=1021,
    )
    assert len(observed) <= 20
    assert sum(len(item["content"]) for item in observed) <= 16000
    assert not any(item["content"] == "失败的消息" for item in observed)


def test_retry_after_failure_keeps_completed_detour_in_same_conversation(repo):
    send(repo, now=1000)
    detached = secrets.token_urlsafe(32)
    assert (
        repo.claim("one", detached, "我想做一个墨水屏玩具", now=1001, detached=True)
        == "claimed"
    )
    assert repo.finish("one", detached, "第一版建议先选 7.5 寸。", None, now=1001)
    failed = secrets.token_urlsafe(32)
    assert repo.claim("one", failed, "选 7.5 寸的。", now=1002) == "claimed"
    repo.fail("one", failed, now=1002, failure_code="timeout")
    observed = []

    assert (
        send(
            repo,
            "选 7.5 寸的。",
            responder=lambda history, *a: (
                observed.extend(history) or CoachAnswer("收到，按 7.5 寸继续。")
            ),
            now=1003,
        )
        == "complete"
    )
    assert any(item["content"] == "我想做一个墨水屏玩具" for item in observed)
    assert any(item["content"] == "第一版建议先选 7.5 寸。" for item in observed)
    assert not any(item["content"] == "选 7.5 寸的。" for item in observed)


def test_adapter_sends_structured_context_and_no_unverified_sources():
    calls = []

    def fake(system, message):
        calls.append((system, json.loads(message)))
        return {
            "status": "success",
            "content": json.dumps(
                {"reply": "学一学", "learning_update": LEARNING}, ensure_ascii=False
            ),
        }

    answer = make_llm_responder(fake)([], "学习", None)
    assert answer.learning_update == LEARNING
    assert calls[0][1]["available_sources"] == []
    assert "掌握" in calls[0][0] and "固定反馈表" in calls[0][0]
    assert "学一学" not in repr(answer)


def test_adapter_accepts_plain_response_without_inventing_progress():
    answer = make_llm_responder(
        lambda *a: {"status": "success", "content": "聊聊今天。"}
    )([], "你好", None)
    assert answer.content == "聊聊今天。" and answer.learning_update is None
    with pytest.raises(RuntimeError, match="unavailable"):
        make_llm_responder(lambda *a: {"status": "error", "message": "private secret"})(
            [], "你好", None
        )


def test_provider_failures_are_classified_without_retaining_provider_text(repo):
    responder = make_llm_responder(
        lambda *a: {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "private",
        }
    )
    assert send(repo, responder=responder, now=1000) == "failed"
    turn = repo.view("one", now=1001)["turns"][0]
    assert turn["status"] == "failed" and turn["failure_code"] == "timeout"


def test_adapter_limits_long_retrieved_excerpts_before_calling_provider():
    observed = []

    def fake(_, payload):
        observed.append(json.loads(payload))
        return {"status": "success", "content": "可以。"}

    make_llm_responder(fake)(
        [],
        "讲解",
        None,
        context={"sources": [{"source_id": "one", "excerpt": "x" * 3000}] * 8},
    )
    sources = observed[0]["available_sources"]
    assert len(sources) == 6 and all(
        len(source["excerpt"]) <= 2000 for source in sources
    )


def test_simulation_is_explicit_and_preserves_anchor_when_chatting():
    first = simulated_responder([], "我想学习时间管理", None)
    assert "模拟回复" in first.content and first.learning_update["topic"] == "时间管理"
    assert (
        simulated_responder([], "聊聊周末", first.learning_update).learning_update
        is None
    )


def test_history_pages_cover_all_records_without_overlap_or_other_users(repo):
    for index in range(87):
        send(
            repo,
            f"本人记录{index}",
            responder=lambda *a: CoachAnswer("回复"),
            now=1000 + index,
        )
        send(repo, "别人的记录", user="two", now=1000 + index)
    page = repo.view("one", now=2000)
    sizes, ids = [], []
    while True:
        sizes.append(len(page["turns"]))
        assert all(
            turn["user_content"].startswith("本人记录") for turn in page["turns"]
        )
        ids.extend(turn["turn_id"] for turn in page["turns"])
        if page["before"] is None:
            break
        page = repo.history_page("one", before=page["before"])
    assert sizes == [40, 40, 7]
    assert len(ids) == len(set(ids)) == 87
    assert repo.history_page("absent", before=max(ids))["turns"] == []


@pytest.mark.parametrize("before", [0, -1, True, "2", 9223372036854775808])
def test_history_cursor_validation(repo, before):
    with pytest.raises(ValueError):
        repo.history_page("one", before=before)
