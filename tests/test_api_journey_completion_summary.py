from fastapi.testclient import TestClient

from api.app import create_app
from learning.evidence import LearningEvidence
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)


def test_completion_summary_api_should_return_completed_journey_results(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    journey = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    ).json()

    start_response = client.post(f"/journeys/{journey['journey_id']}/start")

    session_id = start_response.json()["session_id"]

    session_repository = SQLiteLearningSessionRepository(tmp_path / "sessions.db")
    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")
    journey_repository = SQLiteLearningJourneyRepository(tmp_path / "journeys.db")

    session = session_repository.get_latest_by_journey_for_user(
        journey_id=journey["journey_id"],
        user_id=user["user_id"],
    )

    session.completed = True
    session.understanding_score = 85
    session.difficulty = "已经掌握"
    session.next_step = "完成学习"
    session_repository.save(session)

    evidence_repository.save(
        LearningEvidence(
            session_id=session_id,
            task="完成 Python 综合练习",
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )
    )

    saved_journey = journey_repository.get_by_id(journey["journey_id"])

    saved_journey.status = "completed"
    journey_repository.save(saved_journey)

    response = client.get(
        f"/journeys/{journey['journey_id']}/completion-summary",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["journey_id"] == journey["journey_id"]
    assert data["domain"] == "Python"
    assert data["status"] == "completed"

    assert data["completed_sessions"] == 1
    assert data["latest_understanding"] == 85

    assert data["evidence_count"] == 1
    assert data["completed_tasks"] == 1
    assert data["learning_signal"] == "positive"

    assert data["quality_summary"] == {
        "strong": 1,
        "weak": 0,
        "insufficient": 0,
    }


def test_completion_summary_api_should_reject_active_journey(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    journey = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    response = client.get(
        f"/journeys/{journey['journey_id']}/completion-summary",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "journey must be completed before building completion summary"
    )


def test_completion_summary_api_should_return_404_when_journey_not_found(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    response = client.get(
        "/journeys/missing-journey/completion-summary",
        params={
            "user_id": "missing-user",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "journey not found"
