def build_learning_continuity_context(
    journey_id,
    repository,
    user_id=None,
):
    if user_id is not None:
        latest_session = repository.get_latest_by_journey_for_user(
            journey_id=journey_id,
            user_id=user_id,
        )
    else:
        latest_session = repository.get_latest_by_journey(journey_id)

    if latest_session is None:
        return {
            "has_previous_session": False,
        }

    return {
        "has_previous_session": True,
        "topic": latest_session.topic,
        "completed": latest_session.completed,
        "understanding_score": (latest_session.understanding_score),
        "difficulty": latest_session.difficulty,
        "next_step": latest_session.next_step,
    }
