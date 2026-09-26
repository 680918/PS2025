from fastapi.testclient import TestClient

from api.app import create_app


def test_web_start_journey_should_activate_and_render_success(
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

    response = client.post(f"/web/journeys/{journey['journey_id']}/start")

    assert response.status_code == 200

    assert "学习已开始" in response.text
    assert "英语" in response.text


def test_web_start_journey_should_render_continue_link(
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

    response = client.post(f"/web/journeys/{journey['journey_id']}/start")

    assert response.status_code == 200

    expected_url = (
        f"/web/journeys/{journey['journey_id']}/continue?user_id={user['user_id']}"
    )

    assert "继续学习" in response.text
    assert expected_url in response.text


def test_web_start_journey_should_use_first_curriculum_topic(
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
            "curriculum_topics": [
                "Python开发环境搭建与第一个程序",
                "变量、数据类型与基本输入输出",
            ],
        },
    ).json()

    response = client.post(f"/web/journeys/{journey['journey_id']}/start")

    assert response.status_code == 200
    assert "当前主题：Python开发环境搭建与第一个程序" in response.text
