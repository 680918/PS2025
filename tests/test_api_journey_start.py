from fastapi.testclient import TestClient

from api.app import create_app


def test_start_journey_should_activate_and_create_session(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    # 创建用户
    user_response = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    )

    user = user_response.json()

    # 创建 Journey
    journey_response = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    )

    journey = journey_response.json()

    # 启动 Journey
    response = client.post(f"/journeys/{journey['journey_id']}/start")

    assert response.status_code == 200

    data = response.json()

    assert data["journey_id"] == journey["journey_id"]

    assert data["status"] == "active"

    assert data["session_id"]


def test_start_journey_should_return_404_when_journey_not_found(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.post("/journeys/missing_journey/start")

    assert response.status_code == 404

    assert response.json() == {"detail": "journey not found"}


def test_start_journey_should_return_409_when_already_active(
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
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    ).json()

    url = f"/journeys/{journey['journey_id']}/start"

    first_response = client.post(url)

    assert first_response.status_code == 200

    second_response = client.post(url)

    assert second_response.status_code == 409

    assert second_response.json() == {"detail": "journey already active"}
