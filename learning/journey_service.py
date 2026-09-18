from learning.journey import LearningJourney
from learning.session_service import (
    create_and_save_learning_session,
)


def create_learning_journey(
    repository,
    user_id,
    domain,
    goal,
    user_repository=None,
):
    domain = domain.strip()
    goal = goal.strip()

    if not domain:
        raise ValueError("domain is required")

    if not goal:
        raise ValueError("goal is required")

    if user_repository is not None:
        user = user_repository.get_by_id(user_id)

        if user is None:
            raise ValueError("user not found")

    journey = LearningJourney(
        user_id=user_id,
        domain=domain,
        goal=goal,
    )

    repository.save(journey)

    return journey


def start_learning_journey(
    repository,
    journey,
    session_repository=None,
):
    if journey.status == "active":
        raise ValueError("journey already active")

    if journey.status == "completed":
        raise ValueError("journey already completed")

    journey.status = "active"

    repository.save(journey)

    if session_repository is not None:
        return create_and_save_learning_session(
            repository=session_repository,
            journey_id=journey.journey_id,
            user_id=journey.user_id,
            topic=journey.domain,
        )

    return journey


def complete_learning_journey(
    repository,
    journey,
):
    if journey.status != "active":
        raise ValueError("only active journey can be completed")

    journey.status = "completed"

    repository.save(journey)

    return journey
