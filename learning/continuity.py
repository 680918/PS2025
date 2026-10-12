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
        latest_session = repository.get_latest_by_journey(
            journey_id,
        )

    if latest_session is None:
        return {
            "has_current_session": False,
            "has_previous_session": False,
        }

    if latest_session.completed is False:
        return {
            "has_current_session": True,
            "current_session_id": latest_session.session_id,
            "current_topic": latest_session.topic,
            "current_understanding_score": latest_session.understanding_score,
            "current_difficulty": latest_session.difficulty,
            "current_next_step": latest_session.next_step,
            "has_previous_session": False,
        }

    return {
        "has_current_session": False,
        "has_previous_session": True,
        "session_id": latest_session.session_id,
        "topic": latest_session.topic,
        "completed": latest_session.completed,
        "understanding_score": latest_session.understanding_score,
        "difficulty": latest_session.difficulty,
        "next_step": latest_session.next_step,
    }
