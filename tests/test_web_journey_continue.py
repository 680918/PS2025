from fastapi.testclient import TestClient

from api.app import create_app


def test_web_continue_journey_should_render_previous_learning_context(
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
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    assert "继续学习" in response.text
    assert "英语" in response.text


def test_web_continue_page_should_render_feedback_form(
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
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    assert "提交学习反馈" in response.text
    assert 'name="understanding_score"' in response.text
    assert 'name="difficulty"' in response.text
    assert 'name="next_step"' in response.text


def test_web_continue_page_should_render_coach_next_task(
    tmp_path,
    monkeypatch,
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

    def fake_run_agent(
        user_message,
        **kwargs,
    ):
        return "<script>alert(`test`)</script>今天学习英语"

    monkeypatch.setattr(
        "api.app.run_agent",
        fake_run_agent,
    )

    response = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200
    assert "今天学习什么" in response.text
    assert "&lt;script&gt;" in response.text
    assert "<script>" not in response.text
    assert "今天学习英语" in response.text
