from learning.journey import LearningJourney
from learning.session_service import (
    create_and_save_learning_session,
)
from learning.curriculum import CurriculumItem, LearningCurriculum


def create_learning_journey(
    repository,
    user_id,
    domain,
    goal,
    user_repository=None,
    curriculum_topics=None,
    curriculum_repository=None,
    unit_of_work=None,
):
    domain = domain.strip()
    goal = goal.strip()

    if not domain:
        raise ValueError("domain is required")

    if not goal:
        raise ValueError("goal is required")

    if curriculum_topics is not None:
        if not isinstance(curriculum_topics, list) or not all(
            isinstance(topic, str) for topic in curriculum_topics
        ):
            raise ValueError("curriculum_topics must be a list of strings")

    if curriculum_topics is not None and curriculum_repository is None:
        raise ValueError("curriculum repository is required")

    if user_repository is not None:
        user = user_repository.get_by_id(user_id)

        if user is None:
            raise ValueError("user not found")

    journey = LearningJourney(
        user_id=user_id,
        domain=domain,
        goal=goal,
    )

    curriculum = None

    if curriculum_topics is not None:
        curriculum = LearningCurriculum(
            journey_id=journey.journey_id,
            items=[
                CurriculumItem(
                    position=index,
                    topic=topic,
                )
                for index, topic in enumerate(curriculum_topics, start=1)
            ],
        )

    if curriculum is not None and unit_of_work is not None:
        unit_of_work.save(journey, curriculum)
    else:
        repository.save(journey)

        if curriculum is not None:
            curriculum_repository.save(curriculum)

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
