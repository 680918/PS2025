from fastapi.testclient import TestClient

from api.app import create_app


def test_web_feedback_should_update_session_and_render_success(
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

    response = client.post(
        f"/web/journeys/{journey['journey_id']}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "80",
            "difficulty": "听力速度较快",
            "next_step": "练习慢速英语听力",
        },
    )

    assert response.status_code == 200

    assert "学习反馈已保存" in response.text
    assert "80" in response.text
    assert "听力速度较快" in response.text
    assert "练习慢速英语听力" in response.text


def test_web_feedback_should_appear_on_continue_page(
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

    client.post(
        f"/web/journeys/{journey['journey_id']}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "80",
            "difficulty": "听力速度较快",
            "next_step": "练习慢速英语听力",
        },
    )

    response = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200
    assert "80" in response.text
    assert "听力速度较快" in response.text
    assert "练习慢速英语听力" in response.text


def test_web_feedback_should_reject_other_user(
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

    response = client.post(
        f"/web/journeys/{journey['journey_id']}/feedback",
        data={
            "user_id": user2["user_id"],
            "understanding_score": "80",
            "difficulty": "听力速度较快",
            "next_step": "练习慢速英语听力",
        },
    )

    assert response.status_code == 404

    assert response.json() == {"detail": "journey not found"}
