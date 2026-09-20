import sqlite3
import pytest

from learning.evidence import LearningEvidence
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)
from learning.session import LearningSession
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)


def test_sqlite_evidence_repository_should_persist_and_restore_evidence(
    tmp_path,
):
    database_path = tmp_path / "sessions.db"

    # 1. 初始化 Session 表。
    session_repository = SQLiteLearningSessionRepository(database_path)

    # 2. 创建真实 Session。
    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Python 函数",
    )

    # 3. 保存 Session，确保数据库中存在父记录。
    session_repository.save(session)

    # 4. Evidence Repository 使用同一个数据库文件。
    repository = SQLiteLearningEvidenceRepository(database_path)

    # 5. Evidence 必须引用刚才保存的真实 session_id。
    evidence = LearningEvidence(
        session_id=session.session_id,
        task="编写带参数的 Python 函数",
        result="通过 3 个预定测试",
        assessment="已通过当前练习",
    )

    repository.save(evidence)

    # 6. 重新创建 Repository，验证持久化。
    restored_repository = SQLiteLearningEvidenceRepository(database_path)

    evidences = restored_repository.list_by_session(session.session_id)

    assert len(evidences) == 1

    restored = evidences[0]

    assert restored.evidence_id == evidence.evidence_id
    assert restored.session_id == session.session_id
    assert restored.task == "编写带参数的 Python 函数"
    assert restored.result == "通过 3 个预定测试"


def test_sqlite_evidence_repository_should_isolate_by_session(
    tmp_path,
):
    database_path = tmp_path / "sessions.db"

    # 先创建并保存两个真实 Session。
    session_repository = SQLiteLearningSessionRepository(database_path)

    first_session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Python",
    )

    second_session = LearningSession(
        journey_id="journey_002",
        user_id="user_002",
        topic="英语",
    )

    session_repository.save(first_session)
    session_repository.save(second_session)

    # Evidence Repository 使用同一个数据库。
    repository = SQLiteLearningEvidenceRepository(database_path)

    first = LearningEvidence(
        session_id=first_session.session_id,
        task="练习 Python 函数",
        result="通过测试",
        assessment="完成当前练习",
    )

    second = LearningEvidence(
        session_id=first_session.session_id,
        task="练习异常处理",
        result="通过测试",
        assessment="完成当前练习",
    )

    other_session = LearningEvidence(
        session_id=second_session.session_id,
        task="学习英语听力",
        result="完成听力练习",
        assessment="需要继续训练",
    )

    repository.save(first)
    repository.save(second)
    repository.save(other_session)

    session_one_evidence = repository.list_by_session(first_session.session_id)

    session_two_evidence = repository.list_by_session(second_session.session_id)

    assert len(session_one_evidence) == 2
    assert len(session_two_evidence) == 1

    assert {item.evidence_id for item in session_one_evidence} == {
        first.evidence_id,
        second.evidence_id,
    }

    assert session_two_evidence[0].evidence_id == other_session.evidence_id

    assert all(
        item.session_id == first_session.session_id for item in session_one_evidence
    )

    assert session_two_evidence[0].session_id == second_session.session_id


def test_sqlite_evidence_repository_should_update_existing_evidence(
    tmp_path,
):
    database_path = tmp_path / "sessions.db"

    # 先创建真实 Session，满足 Evidence 的外键约束。
    session_repository = SQLiteLearningSessionRepository(database_path)

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Python 参数边界测试",
    )

    session_repository.save(session)

    # Evidence Repository 使用同一个数据库。
    repository = SQLiteLearningEvidenceRepository(database_path)

    evidence = LearningEvidence(
        session_id=session.session_id,
        task="Python 参数边界测试",
        result="测试失败",
        assessment="需要补强边界处理",
    )

    repository.save(evidence)

    original_id = evidence.evidence_id

    # 修改同一条 Evidence，而不是创建新 Evidence。
    evidence.result = "测试通过"
    evidence.assessment = "已通过当前边界测试"

    repository.save(evidence)

    # 重新创建 Repository，确认修改已持久化。
    restored_repository = SQLiteLearningEvidenceRepository(database_path)

    evidences = restored_repository.list_by_session(session.session_id)

    assert len(evidences) == 1

    restored = evidences[0]

    assert restored.evidence_id == original_id
    assert restored.session_id == session.session_id
    assert restored.result == "测试通过"
    assert restored.assessment == "已通过当前边界测试"


def test_session_and_evidence_repositories_should_share_database(
    tmp_path,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)

    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Python 函数",
    )

    session_repository.save(session)

    evidence = LearningEvidence(
        session_id=session.session_id,
        task="编写带参数的 Python 函数",
        result="通过 3 个预定测试",
        assessment="已通过当前练习",
    )

    evidence_repository.save(evidence)

    restored_repository = SQLiteLearningEvidenceRepository(database_path)

    restored = restored_repository.list_by_session(session.session_id)

    assert len(restored) == 1
    assert restored[0].evidence_id == evidence.evidence_id
    assert restored[0].session_id == session.session_id
    assert restored[0].task == "编写带参数的 Python 函数"


def test_evidence_repository_should_reject_nonexistent_session(
    tmp_path,
):
    database_path = tmp_path / "sessions.db"

    # 先初始化真实 Session 表，但不创建任何 Session。
    SQLiteLearningSessionRepository(database_path)

    repository = SQLiteLearningEvidenceRepository(database_path)

    evidence = LearningEvidence(
        session_id="session_does_not_exist",
        task="Python 函数练习",
        result="通过 3 个测试",
        assessment="已完成当前练习",
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.save(evidence)

    assert repository.list_by_session("session_does_not_exist") == []


def test_sqlite_evidence_repository_should_persist_structured_test_results(
    tmp_path,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Python 函数",
    )

    session_repository.save(session)

    repository = SQLiteLearningEvidenceRepository(database_path)

    evidence = LearningEvidence(
        session_id=session.session_id,
        task="编写带参数的 Python 函数",
        result="完成函数并运行测试",
        assessment="用户认为已掌握",
        tests_passed=3,
        tests_total=4,
    )

    repository.save(evidence)

    restored_repository = SQLiteLearningEvidenceRepository(database_path)

    restored = restored_repository.list_by_session(session.session_id)

    assert len(restored) == 1

    assert restored[0].tests_passed == 3
    assert restored[0].tests_total == 4

    assert restored[0].assessment == "用户认为已掌握"


def test_existing_evidence_table_should_upgrade_without_losing_data(tmp_path):
    database_path = tmp_path / "sessions.db"

    # 先建立真实 Session，保留现有外键关系。
    session_repository = SQLiteLearningSessionRepository(database_path)

    session = LearningSession(
        journey_id="journey_001",
        user_id="user_001",
        topic="Python 函数",
    )
    session_repository.save(session)

    # 模拟旧版本数据库：Evidence 表没有结构化测试结果字段。
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE learning_evidence (
                evidence_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task TEXT NOT NULL,
                result TEXT NOT NULL,
                assessment TEXT NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES learning_sessions(session_id)
            )
            """
        )

        connection.execute(
            """
            INSERT INTO learning_evidence (
                evidence_id,
                session_id,
                task,
                result,
                assessment
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "old_evidence_001",
                session.session_id,
                "旧版 Python 练习",
                "已提交",
                "已完成",
            ),
        )

    # 初始化新版 Repository：预期在这里完成旧表升级。
    repository = SQLiteLearningEvidenceRepository(database_path)

    old_records = repository.list_by_session(session.session_id)

    assert len(old_records) == 1
    assert old_records[0].evidence_id == "old_evidence_001"
    assert old_records[0].task == "旧版 Python 练习"
    assert old_records[0].tests_passed is None
    assert old_records[0].tests_total is None

    new_evidence = LearningEvidence(
        session_id=session.session_id,
        task="新版 Python 练习",
        result="运行 4 项测试",
        assessment="需要补强",
        tests_passed=3,
        tests_total=4,
    )

    repository.save(new_evidence)

    records = repository.list_by_session(session.session_id)

    assert len(records) == 2

    new_record = next(
        item for item in records if item.evidence_id == new_evidence.evidence_id
    )

    assert new_record.tests_passed == 3

    assert new_record.tests_total == 4
