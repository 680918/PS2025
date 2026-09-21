from evaluation.evidence_evaluator import evaluate_evidence


def evaluate_journey_evidence(
    session_repository,
    evidence_repository,
    journey_id,
    user_id,
):
    sessions = session_repository.list_by_journey_for_user(
        journey_id,
        user_id,
    )

    evidences = []

    for session in sessions:
        session_evidences = evidence_repository.list_by_session(
            session.session_id,
        )
        evidences.extend(session_evidences)

    return evaluate_evidence(evidences)
