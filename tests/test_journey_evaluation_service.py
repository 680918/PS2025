from evaluation.journey_evaluation_service import (
    evaluate_journey_from_repository,
)
from learning.session import LearningSession
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)


def test_should_evaluate_journey_from_repository():
    class FakeSessionRepository:
        def __init__(self):
            self.calls = []

        def list_by_journey(self, journey_id):
            self.calls.append(journey_id)

            return [
                LearningSession(
                    journey_id=journey_id,
                    user_id="user-001",
                    topic="英语听力",
                    completed=True,
                    understanding_score=60,
                ),
                LearningSession(
                    journey_id=journey_id,
                    user_id="user-001",
                    topic="英语听力",
                    completed=True,
                    understanding_score=80,
                ),
                LearningSession(
                    journey_id=journey_id,
                    user_id="user-001",
                    topic="英语听力",
                    completed=False,
                ),
            ]

    repository = FakeSessionRepository()

    result = evaluate_journey_from_repository(
        repository=repository,
        journey_id="journey-001",
    )

    assert repository.calls == ["journey-001"]

    assert result["completed_sessions"] == 2
    assert result["first_understanding"] == 60
    assert result["latest_understanding"] == 80
    assert result["understanding_change"] == 20
    assert result["trend"] == "improving"


def test_should_evaluate_journey_with_user_scope():
    class FakeSessionRepository:
        def __init__(self):
            self.calls = []

        def list_by_journey_for_user(
            self,
            journey_id,
            user_id,
        ):
            self.calls.append((journey_id, user_id))

            return [
                LearningSession(
                    journey_id=journey_id,
                    user_id=user_id,
                    topic="英语听力",
                    completed=True,
                    understanding_score=60,
                ),
                LearningSession(
                    journey_id=journey_id,
                    user_id=user_id,
                    topic="英语听力",
                    completed=True,
                    understanding_score=80,
                ),
            ]

    repository = FakeSessionRepository()

    result = evaluate_journey_from_repository(
        repository=repository,
        journey_id="journey-001",
        user_id="user-001",
    )

    assert repository.calls == [("journey-001", "user-001")]

    assert result["completed_sessions"] == 2
    assert result["understanding_change"] == 20
    assert result["trend"] == "improving"


def test_should_evaluate_only_current_user_sessions_from_sqlite(
    tmp_path,
):
    repository = SQLiteLearningSessionRepository(tmp_path / "sessions.db")

    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-a",
            topic="英语听力",
            completed=True,
            understanding_score=60,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-a",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-b",
            topic="英语听力",
            completed=True,
            understanding_score=90,
        ),
    ]

    for session in sessions:
        repository.save(session)

    result = evaluate_journey_from_repository(
        repository=repository,
        journey_id="journey-001",
        user_id="user-a",
    )

    assert result["completed_sessions"] == 2
    assert result["first_understanding"] == 60
    assert result["latest_understanding"] == 80
    assert result["understanding_change"] == 20
    assert result["trend"] == "improving"
