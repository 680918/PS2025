import pytest
from learning.journey import LearningJourney
from learning.journey_completion_summary import (
    build_journey_completion_summary,
    build_journey_completion_summary_from_repositories,
)


def test_build_journey_completion_summary_should_combine_learning_results():
    journey = LearningJourney(
        journey_id="journey_001",
        user_id="user_001",
        domain="Python",
        goal="能够独立编写简单程序",
        status="completed",
    )

    journey_evaluation = {
        "completed_sessions": 2,
        "first_understanding": 60,
        "latest_understanding": 85,
        "understanding_change": 25,
        "trend": "improving",
    }

    evidence_evaluation = {
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    summary = build_journey_completion_summary(
        journey=journey,
        journey_evaluation=journey_evaluation,
        evidence_evaluation=evidence_evaluation,
    )

    assert summary == {
        "journey_id": "journey_001",
        "domain": "Python",
        "goal": "能够独立编写简单程序",
        "status": "completed",
        "completed_sessions": 2,
        "first_understanding": 60,
        "latest_understanding": 85,
        "understanding_change": 25,
        "trend": "improving",
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }


def test_build_journey_completion_summary_should_reject_active_journey():
    journey = LearningJourney(
        journey_id="journey_001",
        user_id="user_001",
        domain="Python",
        goal="能够独立编写简单程序",
        status="active",
    )

    journey_evaluation = {
        "completed_sessions": 1,
        "first_understanding": 60,
        "latest_understanding": 60,
        "understanding_change": None,
        "trend": "insufficient_data",
    }

    evidence_evaluation = {
        "evidence_count": 1,
        "completed_tasks": 1,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 1,
            "weak": 0,
            "insufficient": 0,
        },
    }

    with pytest.raises(
        ValueError,
        match="journey must be completed",
    ):
        build_journey_completion_summary(
            journey=journey,
            journey_evaluation=journey_evaluation,
            evidence_evaluation=evidence_evaluation,
        )


def test_build_journey_completion_summary_from_repositories():
    class FakeJourneyRepository:
        def get_by_id_for_user(self, journey_id, user_id):
            return LearningJourney(
                journey_id=journey_id,
                user_id=user_id,
                domain="Python",
                goal="能够独立编写简单程序",
                status="completed",
            )

    class FakeSession:
        def __init__(
            self,
            session_id,
            understanding_score,
        ):
            self.session_id = session_id
            self.completed = True
            self.understanding_score = understanding_score

    class FakeSessionRepository:
        def list_by_journey_for_user(
            self,
            journey_id,
            user_id,
        ):
            return [
                FakeSession(
                    session_id="session_001",
                    understanding_score=60,
                ),
                FakeSession(
                    session_id="session_002",
                    understanding_score=85,
                ),
            ]

    class FakeEvidence:
        def __init__(self):
            self.assessment = "已完成"
            self.tests_passed = 4
            self.tests_total = 4

    class FakeEvidenceRepository:
        def list_by_session(self, session_id):
            return [FakeEvidence()]

    summary = build_journey_completion_summary_from_repositories(
        journey_repository=FakeJourneyRepository(),
        session_repository=FakeSessionRepository(),
        evidence_repository=FakeEvidenceRepository(),
        journey_id="journey_001",
        user_id="user_001",
    )

    assert summary["status"] == "completed"
    assert summary["completed_sessions"] == 2
    assert summary["first_understanding"] == 60
    assert summary["latest_understanding"] == 85
    assert summary["understanding_change"] == 25
    assert summary["trend"] == "improving"

    assert summary["evidence_count"] == 2
    assert summary["completed_tasks"] == 2
    assert summary["learning_signal"] == "positive"

    assert summary["quality_summary"] == {
        "strong": 2,
        "weak": 0,
        "insufficient": 0,
    }
