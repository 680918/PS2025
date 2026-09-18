from learning.session import LearningSession


def create_learning_session(
    journey_id,
    user_id,
    topic,
    completed=False,
    understanding_score=None,
    difficulty=None,
    next_step=None,
):
    return LearningSession(
        journey_id=journey_id,
        user_id=user_id,
        topic=topic,
        completed=completed,
        understanding_score=understanding_score,
        difficulty=difficulty,
        next_step=next_step,
    )


def create_and_save_learning_session(
    repository,
    journey_id,
    user_id,
    topic,
    completed=False,
    understanding_score=None,
    difficulty=None,
    next_step=None,
):
    session = create_learning_session(
        journey_id=journey_id,
        user_id=user_id,
        topic=topic,
        completed=completed,
        understanding_score=understanding_score,
        difficulty=difficulty,
        next_step=next_step,
    )

    repository.save(session)

    return session
