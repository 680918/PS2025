from conversation.message import ConversationMessage
from conversation.sqlite_repository import (
    SQLiteConversationRepository,
)


def test_sqlite_conversation_repository_should_persist_messages(
    tmp_path,
):
    database_path = tmp_path / "conversation.db"

    repository = SQLiteConversationRepository(
        database_path,
    )

    first = ConversationMessage(
        journey_id="journey-1",
        user_id="user-1",
        role="user",
        content="Memory 有哪两种读取模式？",
    )

    second = ConversationMessage(
        journey_id="journey-1",
        user_id="user-1",
        role="assistant",
        content="第一种是隐式注入，第二种是显式工具调用。",
    )

    repository.save(first)
    repository.save(second)

    reloaded_repository = SQLiteConversationRepository(
        database_path,
    )

    messages = reloaded_repository.list_by_journey(
        journey_id="journey-1",
        user_id="user-1",
    )

    assert len(messages) == 2

    assert messages[0].message_id == first.message_id
    assert messages[0].role == "user"
    assert messages[0].content == first.content

    assert messages[1].message_id == second.message_id
    assert messages[1].role == "assistant"
    assert messages[1].content == second.content


def test_sqlite_conversation_repository_should_isolate_messages_by_user_and_journey(
    tmp_path,
):
    repository = SQLiteConversationRepository(
        tmp_path / "conversation.db",
    )

    expected = ConversationMessage(
        journey_id="journey-1",
        user_id="user-1",
        role="user",
        content="目标消息",
    )

    other_user = ConversationMessage(
        journey_id="journey-1",
        user_id="user-2",
        role="user",
        content="其他用户消息",
    )

    other_journey = ConversationMessage(
        journey_id="journey-2",
        user_id="user-1",
        role="user",
        content="其他 Journey 消息",
    )

    repository.save(expected)
    repository.save(other_user)
    repository.save(other_journey)

    messages = repository.list_by_journey(
        journey_id="journey-1",
        user_id="user-1",
    )

    assert len(messages) == 1
    assert messages[0].message_id == expected.message_id
    assert messages[0].content == "目标消息"
