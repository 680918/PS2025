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


def test_web_learning_loop_should_use_previous_feedback_for_next_coach_task(
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

    start_response = client.post(f"/journeys/{journey['journey_id']}/start")

    assert start_response.status_code == 200

    captured_calls = []

    def fake_run_agent(
        user_message,
        **kwargs,
    ):
        captured_calls.append(kwargs)

        continuity = kwargs["learning_continuity_context"]

        if (
            continuity.get("has_previous_session") is False
            or continuity.get("completed") is False
        ):
            return "第一节：基础英语听力练习"

        return "下一节：针对听力速度较快的问题，进行慢速英语听力练习"

    monkeypatch.setattr(
        "api.app.run_agent",
        fake_run_agent,
    )

    first_continue = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert first_continue.status_code == 200
    assert "基础英语听力练习" in first_continue.text, (
        f"第一次调用 Coach 的参数：{captured_calls[0]!r}\n"
        f"第一次页面内容：{first_continue.text!r}"
    )

    assert "基础英语听力练习" in first_continue.text

    feedback_response = client.post(
        f"/web/journeys/{journey['journey_id']}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "80",
            "difficulty": "听力速度较快",
            "next_step": "练习慢速英语听力",
        },
        follow_redirects=False,
    )

    assert feedback_response.status_code == 200
    assert "学习反馈已保存" in feedback_response.text
    assert "听力速度较快" in feedback_response.text
    assert "练习慢速英语听力" in feedback_response.text

    second_continue = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert second_continue.status_code == 200

    assert "听力速度较快" in second_continue.text
    assert "慢速英语听力练习" in second_continue.text

    second_call = captured_calls[-1]

    continuity = second_call["learning_continuity_context"]

    assert continuity["has_previous_session"] is True

    assert continuity["difficulty"] == "听力速度较快"

    assert continuity["next_step"] == "练习慢速英语听力"
