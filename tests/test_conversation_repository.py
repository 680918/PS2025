from conversation.message import ConversationMessage
from conversation.repository import InMemoryConversationRepository


def test_conversation_repository_should_save_and_list_messages_by_journey():
    repository = InMemoryConversationRepository()

    first = ConversationMessage(
        journey_id="journey-1",
        user_id="user-1",
        role="user",
        content="Memory 应该什么时候读取？",
    )

    second = ConversationMessage(
        journey_id="journey-1",
        user_id="user-1",
        role="assistant",
        content="在调用 LLM 之前读取。",
    )

    other_journey = ConversationMessage(
        journey_id="journey-2",
        user_id="user-1",
        role="user",
        content="另一个 Journey 的消息",
    )

    repository.save(first)
    repository.save(second)
    repository.save(other_journey)

    messages = repository.list_by_journey(
        journey_id="journey-1",
        user_id="user-1",
    )

    assert messages == [
        first,
        second,
    ]


def test_conversation_repository_should_isolate_messages_by_user():
    repository = InMemoryConversationRepository()

    user_one_message = ConversationMessage(
        journey_id="journey-1",
        user_id="user-1",
        role="user",
        content="user-1 message",
    )

    user_two_message = ConversationMessage(
        journey_id="journey-1",
        user_id="user-2",
        role="user",
        content="user-2 message",
    )

    repository.save(user_one_message)
    repository.save(user_two_message)

    messages = repository.list_by_journey(
        journey_id="journey-1",
        user_id="user-1",
    )

    assert messages == [
        user_one_message,
    ]
