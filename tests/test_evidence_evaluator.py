from learning.evidence import LearningEvidence
from evaluation.evidence_evaluator import evaluate_evidence


def test_should_evaluate_positive_learning_signal():

    evidences = [
        LearningEvidence(
            session_id="session_001",
            task="完成Python函数练习",
            result="通过3个测试",
            assessment="已完成",
        ),
        LearningEvidence(
            session_id="session_001",
            task="修改参数错误",
            result="独立完成",
            assessment="掌握",
        ),
    ]

    result = evaluate_evidence(evidences)

    assert result["evidence_count"] == 2

    assert result["learning_signal"] == "positive"

    assert result["completed_tasks"] == 2


def test_empty_evidence_should_return_insufficient_data():
    result = evaluate_evidence([])

    assert result["evidence_count"] == 0
    assert result["completed_tasks"] == 0
    assert result["learning_signal"] == "insufficient_data"


def test_mixed_evidence_should_not_return_positive():
    evidences = [
        LearningEvidence(
            session_id="session_001",
            task="编写普通 Python 函数",
            result="通过 3 个测试",
            assessment="已完成",
        ),
        LearningEvidence(
            session_id="session_001",
            task="参数边界处理",
            result="边界测试失败",
            assessment="需要补强",
        ),
    ]

    result = evaluate_evidence(evidences)

    assert result["evidence_count"] == 2
    assert result["completed_tasks"] == 1
    assert result["learning_signal"] == "insufficient_data"
