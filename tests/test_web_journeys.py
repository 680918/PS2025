from fastapi.testclient import TestClient

from api.app import create_app


def test_web_journey_should_create_journey_and_render_success(
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

    response = client.post(
        "/web/journeys",
        data={
            "user_id": user["user_id"],
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    )

    assert response.status_code == 200

    assert "学习目标创建成功" in response.text
    assert "英语" in response.text
    assert "6个月达到日常交流" in response.text


def test_web_journey_success_page_should_render_start_button(
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

    response = client.post(
        "/web/journeys",
        data={
            "user_id": user["user_id"],
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    )

    assert response.status_code == 200

    assert "开始学习" in response.text
    assert "/web/journeys/" in response.text
    assert "/start" in response.text


def test_web_journey_success_page_should_include_journey_id_in_start_action(
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

    response = client.post(
        "/web/journeys",
        data={
            "user_id": user["user_id"],
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    )

    assert response.status_code == 200

    assert "/web/journeys/" in response.text
    assert "/start" in response.text
