from fastapi.testclient import TestClient

from api.app import create_app


def test_post_users_should_register_user(tmp_path):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "ZHANGSAN@EXAMPLE.COM",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "张三"
    assert data["email"] == "zhangsan@example.com"
    assert data["user_id"]
