from evaluation.journey_evaluator import (
    evaluate_journey_progress,
)


def evaluate_journey_from_repository(
    repository,
    journey_id,
    user_id=None,
):
    if user_id is not None:
        sessions = repository.list_by_journey_for_user(
            journey_id,
            user_id,
        )
    else:
        sessions = repository.list_by_journey(
            journey_id,
        )

    return evaluate_journey_progress(
        sessions=sessions,
    )