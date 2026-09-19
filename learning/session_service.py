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


def update_learning_session_feedback(
    repository,
    session,
    understanding_score,
    difficulty,
    next_step,
):
    if not 0 <= understanding_score <= 100:
        raise ValueError("understanding_score must be between 0 and 100")

    difficulty = difficulty.strip()
    next_step = next_step.strip()

    if not difficulty:
        raise ValueError("difficulty is required")

    if not next_step:
        raise ValueError("next_step is required")

    session.completed = True
    session.understanding_score = understanding_score
    session.difficulty = difficulty
    session.next_step = next_step

    repository.save(session)

    return session
