from fastapi.testclient import TestClient

from api.app import create_app
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)


def test_web_evidence_submission_should_save_to_sqlite(tmp_path):
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

    start_response = client.post(f"/journeys/{journey['journey_id']}/start")

    assert start_response.status_code == 200

    session_id = start_response.json()["session_id"]

    response = client.post(
        f"/web/journeys/{journey['journey_id']}/evidence",
        data={
            "user_id": user["user_id"],
            "session_id": session_id,
            "task": "参数边界处理",
            "result": "4 项测试通过 3 项",
            "assessment": "需继续练习",
            "tests_passed": "3",
            "tests_total": "4",
        },
    )

    assert response.status_code == 200
    assert "练习证据已保存" in response.text

    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")

    records = evidence_repository.list_by_session(session_id)

    assert len(records) == 1
    assert records[0].task == "参数边界处理"
    assert records[0].result == "4 项测试通过 3 项"
    assert records[0].assessment == "需继续练习"
    assert records[0].tests_passed == 3
    assert records[0].tests_total == 4
