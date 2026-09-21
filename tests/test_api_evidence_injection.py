from fastapi.testclient import TestClient

from api.app import create_app
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)


def test_web_continue_should_inject_evidence_repository(
    tmp_path,
    monkeypatch,
):
    captured = {}

    def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return "今天的学习任务"

    monkeypatch.setattr(
        "api.app.run_agent",
        fake_run_agent,
    )

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
            "goal": "学会编写 Python 函数",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    response = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    evidence_repository = captured["learning_evidence_repository"]

    assert isinstance(
        evidence_repository,
        SQLiteLearningEvidenceRepository,
    )

    assert evidence_repository.database_path == (tmp_path / "sessions.db")

    assert captured["journey_id"] == journey["journey_id"]
    assert captured["user_id"] == user["user_id"]

    assert "今天的学习任务" in response.text
