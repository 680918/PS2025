from learning.evidence import LearningEvidence


def submit_learning_evidence(
    session_repository,
    evidence_repository,
    journey_id,
    user_id,
    session_id,
    task,
    result,
    assessment,
    tests_passed=None,
    tests_total=None,
):
    # 只查询指定用户、指定 Journey 下的 Session。
    sessions = session_repository.list_by_journey_for_user(
        journey_id,
        user_id,
    )

    session_ids = {session.session_id for session in sessions}

    # 不区分「Session 不存在」与「Session 属于其他用户」。
    if session_id not in session_ids:
        raise ValueError("session not found")

    if not task.strip():
        raise ValueError("task is required")

    if not result.strip():
        raise ValueError("result is required")

    if not assessment.strip():
        raise ValueError("assessment is required")

    if (tests_passed is None) != (tests_total is None):
        raise ValueError("tests_passed and tests_total must be provided together")

    if tests_total is not None and (type(tests_total) is not int or tests_total <= 0):
        raise ValueError("tests_total must be a positive integer")

    if tests_passed is not None and type(tests_passed) is not int:
        raise ValueError("tests_passed must be an integer")

    if (
        tests_passed is not None
        and tests_total is not None
        and (tests_passed < 0 or tests_passed > tests_total)
    ):
        raise ValueError("tests_passed must be between 0 and tests_total")

    evidence = LearningEvidence(
        session_id=session_id,
        task=task,
        result=result,
        assessment=assessment,
        tests_passed=tests_passed,
        tests_total=tests_total,
    )

    evidence_repository.save(evidence)

    return evidence
