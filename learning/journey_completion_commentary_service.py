from learning.journey_completion_summary import (
    build_journey_completion_summary_from_repositories,
)


def generate_journey_completion_commentary(
    summary,
    commentary_generator,
):
    return commentary_generator.generate(summary)


def generate_journey_completion_commentary_from_repositories(
    journey_repository,
    session_repository,
    evidence_repository,
    journey_id,
    user_id,
    commentary_generator,
):
    summary = build_journey_completion_summary_from_repositories(
        journey_repository=journey_repository,
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id=journey_id,
        user_id=user_id,
    )

    return generate_journey_completion_commentary(
        summary=summary,
        commentary_generator=commentary_generator,
    )
