from fastapi.testclient import TestClient

from api.app import create_app
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)


def test_web_continue_should_show_evidence_submission_form(
    tmp_path,
    monkeypatch,
):
    def fake_run_agent(**kwargs):
        return "今天继续练习 Python 函数"

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

    start_response = client.post(f"/journeys/{journey['journey_id']}/start")

    assert start_response.status_code == 200

    response = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    html = response.text

    assert "提交练习证据" in html
    assert f'action="/web/journeys/{journey["journey_id"]}/evidence"' in html
    assert 'name="task"' in html
    assert 'name="result"' in html
    assert 'name="assessment"' in html
    assert 'name="tests_passed"' in html
    assert 'name="tests_total"' in html


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
