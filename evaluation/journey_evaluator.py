def evaluate_journey_progress(sessions):
    completed_sessions = [session for session in sessions if session.completed is True]

    scores = [
        session.understanding_score
        for session in completed_sessions
        if session.understanding_score is not None
    ]

    first_understanding = scores[0] if scores else None

    latest_understanding = scores[-1] if scores else None

    understanding_change = (
        latest_understanding - first_understanding if len(scores) >= 2 else None
    )

    if understanding_change is None:
        trend = "insufficient_data"
    elif understanding_change >= 5:
        trend = "improving"
    elif understanding_change <= -5:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "completed_sessions": len(completed_sessions),
        "first_understanding": first_understanding,
        "latest_understanding": latest_understanding,
        "understanding_change": understanding_change,
        "trend": trend,
    }
