from types import SimpleNamespace
from unittest.mock import Mock

from learning.evidence import LearningEvidence
from evaluation.journey_evidence_service import (
    evaluate_journey_evidence,
)
from learning.session import LearningSession
from learning.sqlite_session_repository import SQLiteLearningSessionRepository
from learning.sqlite_evidence_repository import SQLiteLearningEvidenceRepository


def test_journey_evidence_should_only_include_requested_user():
    user_session = SimpleNamespace(session_id="session_user_a")

    session_repository = Mock()
    session_repository.list_by_journey_for_user.return_value = [
        user_session,
    ]

    evidence_repository = Mock()
    evidence_repository.list_by_session.return_value = [
        LearningEvidence(
            session_id="session_user_a",
            task="Python 函数练习",
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        ),
    ]

    result = evaluate_journey_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_001",
        user_id="user_a",
    )

    assert result["evidence_count"] == 1
    assert result["completed_tasks"] == 1
    assert result["learning_signal"] == "positive"

    session_repository.list_by_journey_for_user.assert_called_once_with(
        "journey_001",
        "user_a",
    )

    evidence_repository.list_by_session.assert_called_once_with(
        "session_user_a",
    )

    session_repository.list_by_journey.assert_not_called()


def test_journey_evidence_should_isolate_users_with_real_sqlite(tmp_path):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    session_a = LearningSession(
        journey_id="journey_001",
        user_id="user_a",
        topic="Python 函数",
    )

    session_b = LearningSession(
        journey_id="journey_001",
        user_id="user_b",
        topic="Python 函数",
    )

    session_repository.save(session_a)
    session_repository.save(session_b)

    evidence_repository.save(
        LearningEvidence(
            session_id=session_a.session_id,
            task="用户 A 的练习",
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )
    )

    evidence_repository.save(
        LearningEvidence(
            session_id=session_b.session_id,
            task="用户 B 的练习",
            result="4 项测试通过 3 项",
            assessment="掌握",
            tests_passed=3,
            tests_total=4,
        )
    )

    result_a = evaluate_journey_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_001",
        user_id="user_a",
    )

    result_b = evaluate_journey_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_001",
        user_id="user_b",
    )

    assert result_a == {
        "evidence_count": 1,
        "completed_tasks": 1,
        "learning_signal": "positive",
        "quality_summary": {
        "strong": 1,
        "weak": 0,
        "insufficient": 0,
        },       
    }   
    

    assert result_b == {
        "evidence_count": 1,
        "completed_tasks": 0,
        "learning_signal": "insufficient_data",
        "quality_summary": {
        "strong": 0,
        "weak": 0,
        "insufficient": 1,
        },
    }


def test_journey_evidence_should_handle_no_sessions():
    session_repository = Mock()
    session_repository.list_by_journey_for_user.return_value = []

    evidence_repository = Mock()

    result = evaluate_journey_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_001",
        user_id="user_a",
    )

    assert result == {
        "evidence_count": 0,
        "completed_tasks": 0,
        "learning_signal": "insufficient_data",
        "quality_summary": {
        "strong": 0,
        "weak": 0,
        "insufficient": 0,
    },
    }

    evidence_repository.list_by_session.assert_not_called()


def test_journey_evidence_should_aggregate_multiple_sessions():
    session_repository = Mock()

    session_repository.list_by_journey_for_user.return_value = [
        SimpleNamespace(session_id="session_001"),
        SimpleNamespace(session_id="session_002"),
    ]

    evidence_repository = Mock()

    evidence_repository.list_by_session.side_effect = [
        [
            LearningEvidence(
                session_id="session_001",
                task="Python 函数练习",
                result="4 项测试全部通过",
                assessment="已完成",
                tests_passed=4,
                tests_total=4,
            ),
        ],
        [
            LearningEvidence(
                session_id="session_002",
                task="参数边界练习",
                result="4 项测试通过 3 项",
                assessment="掌握",
                tests_passed=3,
                tests_total=4,
            ),
        ],
    ]

    result = evaluate_journey_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_001",
        user_id="user_a",
    )

    assert result == {
        "evidence_count": 2,
        "completed_tasks": 1,
        "learning_signal": "insufficient_data",
        "quality_summary": {
        "strong": 1,
        "weak": 0,
        "insufficient": 1,
    },
    }

    assert evidence_repository.list_by_session.call_count == 2

    evidence_repository.list_by_session.assert_any_call("session_001")

    evidence_repository.list_by_session.assert_any_call("session_002")


def test_journey_evidence_should_aggregate_multiple_sessions_with_real_sqlite(
    tmp_path,
):
    database_path = tmp_path / "sessions.db"

    session_repository = SQLiteLearningSessionRepository(database_path)
    evidence_repository = SQLiteLearningEvidenceRepository(database_path)

    first_session = LearningSession(
        journey_id="journey_001",
        user_id="user_a",
        topic="Python 函数",
    )

    second_session = LearningSession(
        journey_id="journey_001",
        user_id="user_a",
        topic="参数边界处理",
    )

    session_repository.save(first_session)
    session_repository.save(second_session)

    evidence_repository.save(
        LearningEvidence(
            session_id=first_session.session_id,
            task="Python 函数练习",
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )
    )

    evidence_repository.save(
        LearningEvidence(
            session_id=second_session.session_id,
            task="参数边界练习",
            result="4 项测试通过 3 项",
            assessment="掌握",
            tests_passed=3,
            tests_total=4,
        )
    )

    result = evaluate_journey_evidence(
        session_repository=session_repository,
        evidence_repository=evidence_repository,
        journey_id="journey_001",
        user_id="user_a",
    )

    assert result == {
        "evidence_count": 2,
        "completed_tasks": 1,
        "learning_signal": "insufficient_data",
        "quality_summary": {
        "strong": 1,
        "weak": 0,
        "insufficient": 1,
    },
    }
