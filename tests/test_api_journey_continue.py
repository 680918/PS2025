from fastapi.testclient import TestClient

from api.app import create_app


def test_continue_journey_should_restore_previous_learning_context(
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

    client.post(f"/journeys/{journey['journey_id']}/start")

    response = client.get(
        f"/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["has_previous_session"] is True
    assert data["topic"] == "英语"


def test_continue_journey_should_return_404_when_journey_not_found(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.get(
        "/journeys/missing_journey/continue",
        params={
            "user_id": "user_001",
        },
    )

    assert response.status_code == 404

    assert response.json() == {"detail": "journey not found"}


def test_continue_journey_should_reject_other_user(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    user1 = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    user2 = client.post(
        "/users",
        json={
            "name": "李四",
            "email": "lisi@example.com",
        },
    ).json()

    journey = client.post(
        "/journeys",
        json={
            "user_id": user1["user_id"],
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    response = client.get(
        f"/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user2["user_id"],
        },
    )

    assert response.status_code == 404

    assert response.json() == {"detail": "journey not found"}
