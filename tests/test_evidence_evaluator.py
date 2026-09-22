import pytest

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


def test_incomplete_tests_should_not_return_positive():
    evidences = [
        LearningEvidence(
            session_id="session_001",
            task="Python 函数练习",
            result="4 项测试通过 3 项",
            assessment="掌握",
            tests_passed=3,
            tests_total=4,
        ),
    ]

    result = evaluate_evidence(evidences)

    assert result["evidence_count"] == 1
    assert result["completed_tasks"] == 0
    assert result["learning_signal"] == "insufficient_data"


def test_all_passed_tests_should_count_as_completed():
    evidences = [
        LearningEvidence(
            session_id="session_001",
            task="Python 函数练习",
            result="4 项测试全部通过",
            assessment="需要补强",
            tests_passed=4,
            tests_total=4,
        ),
    ]

    result = evaluate_evidence(evidences)

    assert result["evidence_count"] == 1
    assert result["completed_tasks"] == 1
    assert result["learning_signal"] == "positive"


def test_zero_total_tests_should_not_count_as_completed():
    evidences = [
        LearningEvidence(
            session_id="session_001",
            task="Python 函数练习",
            result="尚未运行测试",
            assessment="掌握",
            tests_passed=0,
            tests_total=0,
        ),
    ]

    result = evaluate_evidence(evidences)

    assert result["evidence_count"] == 1
    assert result["completed_tasks"] == 0
    assert result["learning_signal"] == "insufficient_data"


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (3, None),
        (None, 4),
    ],
)
def test_partial_test_results_should_not_count_as_completed(
    tests_passed,
    tests_total,
):
    evidence = LearningEvidence(
        session_id="session_001",
        task="Python 函数练习",
        result="测试结果记录不完整",
        assessment="掌握",
        tests_passed=tests_passed,
        tests_total=tests_total,
    )

    result = evaluate_evidence([evidence])

    assert result["evidence_count"] == 1
    assert result["completed_tasks"] == 0
    assert result["learning_signal"] == "insufficient_data"


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (5, 4),
        (-1, 4),
        (0, -1),
    ],
)
def test_invalid_test_counts_should_not_count_as_completed(
    tests_passed,
    tests_total,
):
    evidence = LearningEvidence(
        session_id="session_001",
        task="Python 函数练习",
        result="测试数量异常",
        assessment="掌握",
        tests_passed=tests_passed,
        tests_total=tests_total,
    )

    result = evaluate_evidence([evidence])

    assert result["completed_tasks"] == 0
    assert result["learning_signal"] == "insufficient_data"


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (1.5, 1.5),
        ("4", "4"),
    ],
)
def test_non_integer_test_counts_should_not_count_as_completed(
    tests_passed,
    tests_total,
):
    evidence = LearningEvidence(
        session_id="session_001",
        task="Python 函数练习",
        result="测试数量类型异常",
        assessment="掌握",
        tests_passed=tests_passed,
        tests_total=tests_total,
    )

    result = evaluate_evidence([evidence])

    assert result["completed_tasks"] == 0
    assert result["learning_signal"] == "insufficient_data"


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (True, 1),
        (1, True),
        (True, True),
        (False, False),
    ],
)
def test_boolean_test_counts_should_not_count_as_completed(
    tests_passed,
    tests_total,
):
    evidence = LearningEvidence(
        session_id="session_001",
        task="Python 函数练习",
        result="测试数量类型异常",
        assessment="掌握",
        tests_passed=tests_passed,
        tests_total=tests_total,
    )

    result = evaluate_evidence([evidence])

    assert result["completed_tasks"] == 0
    assert result["learning_signal"] == "insufficient_data"


def test_all_passed_structured_tests_should_have_strong_evidence_quality():
    evidence = LearningEvidence(
        session_id="session_001",
        task="实现 Evidence Submission",
        result="全部测试通过",
        assessment="已完成",
        tests_passed=10,
        tests_total=10,
    )

    result = evaluate_evidence([evidence])

    assert result["quality_summary"] == {
        "strong": 1,
        "weak": 0,
        "insufficient": 0,
    }


def test_completed_assessment_without_structured_tests_should_have_weak_quality():
    evidence = LearningEvidence(
        session_id="session_001",
        task="理解 Evidence Submission",
        result="能够说明基本概念",
        assessment="掌握",
    )

    result = evaluate_evidence([evidence])

    assert result["completed_tasks"] == 1
    assert result["quality_summary"] == {
        "strong": 0,
        "weak": 1,
        "insufficient": 0,
    }


def test_mixed_evidence_should_preserve_quality_distribution():
    evidences = [
        LearningEvidence(
            session_id="session_001",
            task="实现 Evidence Submission",
            result="全部测试通过",
            assessment="已完成",
            tests_passed=10,
            tests_total=10,
        ),
        LearningEvidence(
            session_id="session_001",
            task="理解 Evidence Submission 原理",
            result="能够说明基本概念",
            assessment="掌握",
        ),
    ]

    result = evaluate_evidence(evidences)

    assert result["quality_summary"] == {
        "strong": 1,
        "weak": 1,
        "insufficient": 0,
    }


def test_incomplete_structured_tests_should_be_counted_as_insufficient_quality():
    evidence = LearningEvidence(
        session_id="session_001",
        task="实现 Evidence Quality",
        result="4 项测试通过 3 项",
        assessment="掌握",
        tests_passed=3,
        tests_total=4,
    )

    result = evaluate_evidence([evidence])

    assert result["quality_summary"] == {
        "strong": 0,
        "weak": 0,
        "insufficient": 1,
    }


def test_quality_summary_should_account_for_every_evidence():
    evidences = [
        LearningEvidence(
            session_id="session_001",
            task="任务 A",
            result="全部测试通过",
            assessment="已完成",
            tests_passed=5,
            tests_total=5,
        ),
        LearningEvidence(
            session_id="session_001",
            task="任务 B",
            result="能够说明概念",
            assessment="掌握",
        ),
        LearningEvidence(
            session_id="session_001",
            task="任务 C",
            result="部分测试通过",
            assessment="掌握",
            tests_passed=3,
            tests_total=4,
        ),
    ]

    result = evaluate_evidence(evidences)

    assert sum(result["quality_summary"].values()) == result["evidence_count"]
