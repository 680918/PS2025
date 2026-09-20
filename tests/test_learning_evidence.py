from learning.evidence import LearningEvidence


def test_learning_evidence_should_store_task_result_and_assessment():
    evidence = LearningEvidence(
        session_id="session-001",
        task="编写带参数的 Python 函数",
        result="通过 3 个预定测试",
        assessment="已通过当前练习，尚未验证迁移能力",
    )

    assert evidence.session_id == "session-001"
    assert evidence.task == "编写带参数的 Python 函数"
    assert evidence.result == "通过 3 个预定测试"
    assert evidence.assessment == "已通过当前练习，尚未验证迁移能力"


def test_learning_evidence_should_have_unique_identity():
    first = LearningEvidence(
        session_id="session-001",
        task="练习 A",
        result="通过 3 个测试",
        assessment="完成当前练习",
    )

    second = LearningEvidence(
        session_id="session-001",
        task="练习 B",
        result="参数边界测试失败",
        assessment="需要补强参数边界处理",
    )

    assert first.evidence_id
    assert second.evidence_id

    assert first.evidence_id != second.evidence_id

    assert first.session_id == second.session_id


def test_learning_evidence_should_store_structured_test_results():
    evidence = LearningEvidence(
        session_id="session-001",
        task="编写带参数的 Python 函数",
        result="完成函数并运行测试",
        assessment="用户认为已掌握",
        tests_passed=3,
        tests_total=4,
    )

    assert evidence.tests_passed == 3
    assert evidence.tests_total == 4
    assert evidence.assessment == "用户认为已掌握"
