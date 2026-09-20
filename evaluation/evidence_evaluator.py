def evaluate_evidence(evidences):
    evidence_count = len(evidences)

    completed_tasks = sum(
        evidence.assessment in {"已完成", "掌握"} for evidence in evidences
    )

    if evidence_count > 0 and completed_tasks == evidence_count:
        learning_signal = "positive"
    else:
        learning_signal = "insufficient_data"

    return {
        "evidence_count": evidence_count,
        "completed_tasks": completed_tasks,
        "learning_signal": learning_signal,
    }
