def evaluate_evidence(evidences):
    evidence_count = len(evidences)

    completed_tasks = 0

    for evidence in evidences:
        if evidence.tests_passed is None and evidence.tests_total is None:
            # 兼容没有结构化测试结果的旧 Evidence。
            is_completed = evidence.assessment in {"已完成", "掌握"}

        elif evidence.tests_passed is None or evidence.tests_total is None:
            # 只填写了一个测试字段：记录不完整，不计入完成。
            is_completed = False

        else:
            # 两个字段都有值：先校验类型，再判断测试结果。
            valid_counts = (
                type(evidence.tests_passed) is int
                and type(evidence.tests_total) is int
                and evidence.tests_total > 0
                and 0 <= evidence.tests_passed <= evidence.tests_total
            )

            is_completed = (
                valid_counts and evidence.tests_passed == evidence.tests_total
            )

        completed_tasks += int(is_completed)

    if evidence_count > 0 and completed_tasks == evidence_count:
        learning_signal = "positive"
    else:
        learning_signal = "insufficient_data"

    return {
        "evidence_count": evidence_count,
        "completed_tasks": completed_tasks,
        "learning_signal": learning_signal,
    }
