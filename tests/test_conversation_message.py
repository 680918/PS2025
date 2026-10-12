from conversation.message import ConversationMessage


def test_conversation_message_should_capture_turn_identity_and_content():
    message = ConversationMessage(
        journey_id="journey-1",
        user_id="user-1",
        role="user",
        content="Memory 应该什么时候读取？",
    )

    assert message.journey_id == "journey-1"
    assert message.user_id == "user-1"
    assert message.role == "user"
    assert message.content == "Memory 应该什么时候读取？"
    assert message.message_id
    assert message.created_at.tzinfo is not None
