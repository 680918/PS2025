from fastapi.testclient import TestClient

from api.app import create_app
from conversation.sqlite_repository import (
    SQLiteConversationRepository,
)


def test_web_message_should_persist_user_and_assistant_turns(
    tmp_path,
    monkeypatch,
):
    app = create_app(
        database_dir=tmp_path,
        learning_feedback_extractor=None,
    )
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "conversation-persistence@example.com",
        },
    ).json()

    journey = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "AI Agent",
            "goal": "学习 Tool Calling 与 Memory",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    monkeypatch.setattr(
        "api.app.run_agent",
        lambda user_message, **kwargs: "Coach response",
    )

    response = client.post(
        f"/web/journeys/{journey['journey_id']}/message",
        data={
            "user_id": user["user_id"],
            "message": "Memory 应该什么时候读取？",
        },
    )

    assert response.status_code == 200

    repository = SQLiteConversationRepository(
        tmp_path / "conversations.db",
    )

    messages = repository.list_by_journey(
        journey_id=journey["journey_id"],
        user_id=user["user_id"],
    )

    assert len(messages) == 2

    assert messages[0].role == "user"
    assert messages[0].content == "Memory 应该什么时候读取？"

    assert messages[1].role == "assistant"
    assert messages[1].content == "Coach response"


def test_web_message_should_pass_previous_conversation_to_agent(
    tmp_path,
    monkeypatch,
):
    app = create_app(
        database_dir=tmp_path,
        learning_feedback_extractor=None,
    )
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "conversation-history@example.com",
        },
    ).json()

    journey = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "AI Agent",
            "goal": "学习 Tool Calling 与 Memory",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    captured_contexts = []

    def fake_run_agent(
        user_message,
        **kwargs,
    ):
        captured_contexts.append(kwargs.get("conversation_context"))

        if len(captured_contexts) == 1:
            return "第一轮 Coach response"

        return "第二轮 Coach response"

    monkeypatch.setattr(
        "api.app.run_agent",
        fake_run_agent,
    )

    first_response = client.post(
        f"/web/journeys/{journey['journey_id']}/message",
        data={
            "user_id": user["user_id"],
            "message": "Memory 有哪两种读取模式？",
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/web/journeys/{journey['journey_id']}/message",
        data={
            "user_id": user["user_id"],
            "message": "那第二种呢？",
        },
    )

    assert second_response.status_code == 200

    assert captured_contexts[0] == []

    assert captured_contexts[1] == [
        {
            "role": "user",
            "content": "Memory 有哪两种读取模式？",
        },
        {
            "role": "assistant",
            "content": "第一轮 Coach response",
        },
    ]


def test_web_message_should_render_conversation_history(
    tmp_path,
    monkeypatch,
):
    app = create_app(
        database_dir=tmp_path,
        learning_feedback_extractor=None,
    )
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "conversation-render@example.com",
        },
    ).json()

    journey = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "AI Agent",
            "goal": "学习 Tool Calling 与 Memory",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    responses = iter(
        [
            "第一轮回答：第二种是显式工具调用。",
            "第二轮回答：它由模型按需触发。",
        ]
    )

    monkeypatch.setattr(
        "api.app.run_agent",
        lambda user_message, **kwargs: next(responses),
    )

    client.post(
        f"/web/journeys/{journey['journey_id']}/message",
        data={
            "user_id": user["user_id"],
            "message": "Memory 有哪两种读取模式？",
        },
    )

    response = client.post(
        f"/web/journeys/{journey['journey_id']}/message",
        data={
            "user_id": user["user_id"],
            "message": "那第二种呢？",
        },
    )

    assert response.status_code == 200

    assert "Memory 有哪两种读取模式？" in response.text
    assert "第一轮回答：第二种是显式工具调用。" in response.text
    assert "那第二种呢？" in response.text
    assert "第二轮回答：它由模型按需触发。" in response.text


def test_web_continue_should_render_existing_conversation_history(
    tmp_path,
    monkeypatch,
):
    app = create_app(
        database_dir=tmp_path,
        learning_feedback_extractor=None,
    )
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "conversation-continue-history@example.com",
        },
    ).json()

    journey = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "AI Agent",
            "goal": "学习 Tool Calling 与 Memory",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    monkeypatch.setattr(
        "api.app.run_agent",
        lambda user_message, **kwargs: "Coach history response",
    )

    client.post(
        f"/web/journeys/{journey['journey_id']}/message",
        data={
            "user_id": user["user_id"],
            "message": "Memory 应该什么时候读取？",
        },
    )

    response = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200
    assert "Memory 应该什么时候读取？" in response.text
    assert "Coach history response" in response.text
