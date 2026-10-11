def build_learning_context(
    journey_repository,
    journey_id,
):
    if journey_id is None:
        return {}

    journey = journey_repository.get_by_id(
        journey_id,
    )

    if journey is None:
        return {}

    return {
        "domain": journey.domain,
        "goal": journey.goal,
        "status": journey.status,
    }
