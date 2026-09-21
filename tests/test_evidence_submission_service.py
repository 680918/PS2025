import pytest

from learning.evidence_submission_service import submit_learning_evidence
from learning.session import LearningSession
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)


def test_submit_evidence_should_reject_other_users_session(tmp_path):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    # 真实 Session 属于用户 B。
    session_b = LearningSession(
        journey_id="journey_b",
        user_id="user_b",
        topic="Python 函数",
    )
    session_repository.save(session_b)

    # 用户 A 尝试向用户 B 的 Session 提交练习证据。
    with pytest.raises(ValueError, match="session not found"):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_b",
            user_id="user_a",
            session_id=session_b.session_id,
            task="Python 函数练习",
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )

    # 不只检查抛错，还确认数据库没有发生越权写入。
    assert evidence_repository.list_by_session(session_b.session_id) == []


def test_submit_evidence_should_save_for_session_owner(tmp_path):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    evidence = submit_learning_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_a",
        user_id="user_a",
        session_id=session.session_id,
        task="参数边界处理",
        result="4 项测试通过 3 项",
        assessment="掌握",
        tests_passed=3,
        tests_total=4,
    )

    records = evidence_repository.list_by_session(session.session_id)

    assert len(records) == 1

    saved = records[0]

    assert saved.evidence_id == evidence.evidence_id
    assert saved.session_id == session.session_id
    assert saved.task == "参数边界处理"
    assert saved.result == "4 项测试通过 3 项"
    assert saved.assessment == "掌握"
    assert saved.tests_passed == 3
    assert saved.tests_total == 4


def test_submit_evidence_should_reject_other_journeys_session(tmp_path):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    # Session 属于用户 A，但属于 Journey A。
    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    # 用户正确，但提交时指定了另一个 Journey。
    with pytest.raises(ValueError, match="session not found"):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_b",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )

    # 拒绝后，数据库不应留下记录。
    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize("task", ["", "   "])
def test_submit_evidence_should_reject_blank_task(tmp_path, task):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(ValueError, match="task is required"):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task=task,
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize("result", ["", "   "])
def test_submit_evidence_should_reject_blank_result(tmp_path, result):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(ValueError, match="result is required"):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result=result,
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize("assessment", ["", "   "])
def test_submit_evidence_should_reject_blank_assessment(
    tmp_path,
    assessment,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(ValueError, match="assessment is required"):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result="4 项测试全部通过",
            assessment=assessment,
            tests_passed=4,
            tests_total=4,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize("tests_total", [0, -1])
def test_submit_evidence_should_reject_nonpositive_tests_total(
    tmp_path,
    tests_total,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(
        ValueError,
        match="tests_total must be a positive integer",
    ):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result="尚未通过测试",
            assessment="需继续练习",
            tests_passed=0,
            tests_total=tests_total,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize("tests_total", [True, 1.5, "4"])
def test_submit_evidence_should_reject_noninteger_tests_total(
    tmp_path,
    tests_total,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(
        ValueError,
        match="tests_total must be a positive integer",
    ):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result="测试尚未全部通过",
            assessment="需继续练习",
            tests_passed=0,
            tests_total=tests_total,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (-1, 4),
        (5, 4),
    ],
)
def test_submit_evidence_should_reject_out_of_range_tests_passed(
    tmp_path,
    tests_passed,
    tests_total,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(
        ValueError,
        match="tests_passed must be between 0 and tests_total",
    ):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result="测试尚未全部通过",
            assessment="需继续练习",
            tests_passed=tests_passed,
            tests_total=tests_total,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize("tests_passed", [True, 1.5, "3"])
def test_submit_evidence_should_reject_noninteger_tests_passed(
    tmp_path,
    tests_passed,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(
        ValueError,
        match="tests_passed must be an integer",
    ):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result="测试尚未全部通过",
            assessment="需继续练习",
            tests_passed=tests_passed,
            tests_total=4,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (3, None),
        (None, 4),
    ],
)
def test_submit_evidence_should_require_both_test_counts(
    tmp_path,
    tests_passed,
    tests_total,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    with pytest.raises(
        ValueError,
        match="tests_passed and tests_total must be provided together",
    ):
        submit_learning_evidence(
            session_repository=session_repository,
            evidence_repository=evidence_repository,
            journey_id="journey_a",
            user_id="user_a",
            session_id=session.session_id,
            task="参数边界处理",
            result="测试尚未全部通过",
            assessment="需继续练习",
            tests_passed=tests_passed,
            tests_total=tests_total,
        )

    assert evidence_repository.list_by_session(session.session_id) == []


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (None, None),
        (0, 4),
    ],
)
def test_submit_evidence_should_accept_valid_test_count_boundaries(
    tmp_path,
    tests_passed,
    tests_total,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_a",
        user_id="user_a",
        topic="Python 函数",
    )
    session_repository.save(session)

    evidence = submit_learning_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_a",
        user_id="user_a",
        session_id=session.session_id,
        task="参数边界处理",
        result="记录本次练习结果",
        assessment="需继续练习",
        tests_passed=tests_passed,
        tests_total=tests_total,
    )

    records = evidence_repository.list_by_session(session.session_id)

    assert len(records) == 1
    assert records[0].evidence_id == evidence.evidence_id
    assert records[0].tests_passed == tests_passed
    assert records[0].tests_total == tests_total
