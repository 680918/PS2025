from conversation.context import build_conversation_context
from conversation.message import ConversationMessage
from conversation.repository import InMemoryConversationRepository


def test_conversation_context_should_return_recent_messages_in_order():
    repository = InMemoryConversationRepository()

    repository.save(
        ConversationMessage(
            journey_id="journey-1",
            user_id="user-1",
            role="user",
            content="Memory 应该什么时候读取？",
        )
    )

    repository.save(
        ConversationMessage(
            journey_id="journey-1",
            user_id="user-1",
            role="assistant",
            content="在调用 LLM 之前读取。",
        )
    )

    context = build_conversation_context(
        repository=repository,
        journey_id="journey-1",
        user_id="user-1",
    )

    assert context == [
        {
            "role": "user",
            "content": "Memory 应该什么时候读取？",
        },
        {
            "role": "assistant",
            "content": "在调用 LLM 之前读取。",
        },
    ]


def test_conversation_context_should_limit_to_recent_messages():
    repository = InMemoryConversationRepository()

    repository.save(
        ConversationMessage(
            journey_id="journey-1",
            user_id="user-1",
            role="user",
            content="第一条",
        )
    )

    repository.save(
        ConversationMessage(
            journey_id="journey-1",
            user_id="user-1",
            role="assistant",
            content="第二条",
        )
    )

    repository.save(
        ConversationMessage(
            journey_id="journey-1",
            user_id="user-1",
            role="user",
            content="第三条",
        )
    )

    context = build_conversation_context(
        repository=repository,
        journey_id="journey-1",
        user_id="user-1",
        recent_limit=2,
    )

    assert context == [
        {
            "role": "assistant",
            "content": "第二条",
        },
        {
            "role": "user",
            "content": "第三条",
        },
    ]
