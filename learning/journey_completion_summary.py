from evaluation.journey_evaluation_service import (
    evaluate_journey_from_repository,
)
from evaluation.journey_evidence_service import (
    evaluate_journey_evidence,
)


class JourneyNotFoundError(ValueError):
    pass


class JourneyNotCompletedError(ValueError):
    pass


def build_journey_completion_summary(
    journey,
    journey_evaluation,
    evidence_evaluation,
):
    if journey.status != "completed":
        raise JourneyNotCompletedError(
            "journey must be completed before building completion summary"
        )

    return {
        "journey_id": journey.journey_id,
        "domain": journey.domain,
        "goal": journey.goal,
        "status": journey.status,
        "completed_sessions": journey_evaluation["completed_sessions"],
        "first_understanding": journey_evaluation["first_understanding"],
        "latest_understanding": journey_evaluation["latest_understanding"],
        "understanding_change": journey_evaluation["understanding_change"],
        "trend": journey_evaluation["trend"],
        "evidence_count": evidence_evaluation["evidence_count"],
        "completed_tasks": evidence_evaluation["completed_tasks"],
        "learning_signal": evidence_evaluation["learning_signal"],
        "quality_summary": evidence_evaluation["quality_summary"],
    }


def build_journey_completion_summary_from_repositories(
    journey_repository,
    session_repository,
    evidence_repository,
    journey_id,
    user_id,
):
    journey = journey_repository.get_by_id_for_user(
        journey_id=journey_id,
        user_id=user_id,
    )

    if journey is None:
        raise JourneyNotFoundError("journey not found")

    journey_evaluation = evaluate_journey_from_repository(
        repository=session_repository,
        journey_id=journey_id,
        user_id=user_id,
    )

    evidence_evaluation = evaluate_journey_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id=journey_id,
        user_id=user_id,
    )

    return build_journey_completion_summary(
        journey=journey,
        journey_evaluation=journey_evaluation,
        evidence_evaluation=evidence_evaluation,
    )
