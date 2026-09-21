import pytest

from fastapi.testclient import TestClient

from api.app import create_app
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)


def test_submit_evidence_api_should_save_to_sqlite(tmp_path):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    )
    assert user_response.status_code == 201
    user = user_response.json()

    journey_response = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "学会编写 Python 函数",
        },
    )
    assert journey_response.status_code == 201
    journey = journey_response.json()

    start_response = client.post(f"/journeys/{journey['journey_id']}/start")
    assert start_response.status_code == 200
    session_id = start_response.json()["session_id"]

    response = client.post(
        f"/journeys/{journey['journey_id']}/evidence",
        json={
            "user_id": user["user_id"],
            "session_id": session_id,
            "task": "参数边界处理",
            "result": "4 项测试通过 3 项",
            "assessment": "需继续练习",
            "tests_passed": 3,
            "tests_total": 4,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["evidence_id"]
    assert data["session_id"] == session_id
    assert data["task"] == "参数边界处理"
    assert data["tests_passed"] == 3
    assert data["tests_total"] == 4

    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")
    records = evidence_repository.list_by_session(session_id)

    assert len(records) == 1
    assert records[0].evidence_id == data["evidence_id"]
    assert records[0].result == "4 项测试通过 3 项"


def test_submit_evidence_api_should_reject_other_users_session(tmp_path):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user_a = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    user_b = client.post(
        "/users",
        json={
            "name": "李四",
            "email": "lisi@example.com",
        },
    ).json()

    journey_b = client.post(
        "/journeys",
        json={
            "user_id": user_b["user_id"],
            "domain": "Python",
            "goal": "学会编写 Python 函数",
        },
    ).json()

    start_response = client.post(f"/journeys/{journey_b['journey_id']}/start")

    assert start_response.status_code == 200

    session_id = start_response.json()["session_id"]

    response = client.post(
        f"/journeys/{journey_b['journey_id']}/evidence",
        json={
            "user_id": user_a["user_id"],
            "session_id": session_id,
            "task": "参数边界处理",
            "result": "4 项测试全部通过",
            "assessment": "已完成",
            "tests_passed": 4,
            "tests_total": 4,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "session not found"}

    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")

    assert evidence_repository.list_by_session(session_id) == []


def test_submit_evidence_api_should_reject_other_journeys_session(tmp_path):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    journey_a = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "学会编写 Python 函数",
        },
    ).json()

    journey_b = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "英语",
            "goal": "提高英语听力",
        },
    ).json()

    start_response = client.post(f"/journeys/{journey_a['journey_id']}/start")

    assert start_response.status_code == 200

    session_id = start_response.json()["session_id"]

    response = client.post(
        f"/journeys/{journey_b['journey_id']}/evidence",
        json={
            "user_id": user["user_id"],
            "session_id": session_id,
            "task": "参数边界处理",
            "result": "4 项测试全部通过",
            "assessment": "已完成",
            "tests_passed": 4,
            "tests_total": 4,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "session not found"}

    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")

    assert evidence_repository.list_by_session(session_id) == []


def test_submit_evidence_api_should_reject_blank_task(tmp_path):
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
        f"/journeys/{journey['journey_id']}/evidence",
        json={
            "user_id": user["user_id"],
            "session_id": session_id,
            "task": "   ",
            "result": "4 项测试全部通过",
            "assessment": "已完成",
            "tests_passed": 4,
            "tests_total": 4,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "task is required"}

    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")

    assert evidence_repository.list_by_session(session_id) == []


def test_submit_evidence_api_should_reject_nonpositive_tests_total(tmp_path):
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
        f"/journeys/{journey['journey_id']}/evidence",
        json={
            "user_id": user["user_id"],
            "session_id": session_id,
            "task": "参数边界处理",
            "result": "测试尚未全部通过",
            "assessment": "需继续练习",
            "tests_passed": 0,
            "tests_total": 0,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "tests_total must be a positive integer"}

    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")

    assert evidence_repository.list_by_session(session_id) == []


def test_submit_evidence_api_should_reject_missing_required_field(tmp_path):
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
        f"/journeys/{journey['journey_id']}/evidence",
        json={
            "user_id": user["user_id"],
            "session_id": session_id,
            # 故意缺少 task
            "result": "4 项测试全部通过",
            "assessment": "已完成",
            "tests_passed": 4,
            "tests_total": 4,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "task is required"}


@pytest.mark.parametrize(
    ("tests_passed", "tests_total"),
    [
        (3, None),
        (None, 4),
    ],
)
def test_submit_evidence_api_should_require_both_test_counts(
    tmp_path,
    tests_passed,
    tests_total,
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
            "goal": "学会编写 Python 函数",
        },
    ).json()

    start_response = client.post(f"/journeys/{journey['journey_id']}/start")

    assert start_response.status_code == 200

    session_id = start_response.json()["session_id"]

    response = client.post(
        f"/journeys/{journey['journey_id']}/evidence",
        json={
            "user_id": user["user_id"],
            "session_id": session_id,
            "task": "参数边界处理",
            "result": "记录本次测试结果",
            "assessment": "需继续练习",
            "tests_passed": tests_passed,
            "tests_total": tests_total,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "tests_passed and tests_total must be provided together"
    }
