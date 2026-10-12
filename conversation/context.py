def build_conversation_context(
    repository,
    journey_id,
    user_id,
    recent_limit=None,
):
    messages = repository.list_by_journey(
        journey_id=journey_id,
        user_id=user_id,
    )

    if recent_limit is not None:
        messages = messages[-recent_limit:]

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]
