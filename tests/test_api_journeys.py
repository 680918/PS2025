from fastapi.testclient import TestClient

from api.app import create_app


def test_post_journeys_should_create_learning_journey(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    )

    user = user_response.json()

    response = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["user_id"] == user["user_id"]

    assert data["domain"] == "英语"

    assert data["goal"] == "6个月达到日常交流"
