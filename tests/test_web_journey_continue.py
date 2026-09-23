from fastapi.testclient import TestClient
from api.app import create_app
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)


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


def test_web_continue_should_forward_curriculum_repository_to_agent(
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
            "domain": "Python",
            "goal": "掌握 Python 编程",
        },
    ).json()

    client.post(f"/journeys/{journey['journey_id']}/start")

    captured = {}

    def fake_run_agent(
        user_message,
        **kwargs,
    ):
        captured.update(kwargs)
        return "今天学习 Python"

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

    curriculum_repository = captured.get("learning_curriculum_repository")

    assert curriculum_repository is not None


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


def test_web_continue_should_create_new_session_after_previous_completed(
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

    def fake_run_agent(user_message, **kwargs):
        return "今天进行慢速英语听力练习"

    monkeypatch.setattr(
        "api.app.run_agent",
        fake_run_agent,
    )

    # 先完成第一节。
    feedback_response = client.post(
        f"/web/journeys/{journey['journey_id']}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "80",
            "difficulty": "听力速度较快",
            "next_step": "练习慢速英语听力",
        },
    )

    assert feedback_response.status_code == 200

    # 再次打开 continue。
    response = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    # 再次提交反馈。
    second_feedback = client.post(
        f"/web/journeys/{journey['journey_id']}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "90",
            "difficulty": "个别句子仍听不清",
            "next_step": "练习正常语速英语",
        },
    )

    assert second_feedback.status_code == 200
    assert "90" in second_feedback.text
    assert "个别句子仍听不清" in second_feedback.text

    repository = SQLiteLearningSessionRepository(tmp_path / "sessions.db")

    sessions = repository.list_by_journey(journey["journey_id"])

    assert len(sessions) == 2

    first_session = sessions[0]
    second_session = sessions[1]

    assert first_session.session_id != second_session.session_id

    assert first_session.completed is True
    assert first_session.understanding_score == 80
    assert first_session.difficulty == "听力速度较快"
    assert first_session.next_step == "练习慢速英语听力"

    assert second_session.completed is True
    assert second_session.understanding_score == 90
    assert second_session.difficulty == "个别句子仍听不清"
    assert second_session.next_step == "练习正常语速英语"


def test_web_continue_should_pass_evaluation_dependencies_to_agent(
    tmp_path,
    monkeypatch,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "测试用户",
            "email": "evaluation-web@example.com",
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

    captured = {}

    def fake_run_agent(user_message, **kwargs):
        captured.update(kwargs)
        return "今天练习英语听力"

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

    assert captured["journey_id"] == journey["journey_id"]
    assert captured["user_id"] == user["user_id"]

    repository = captured["learning_session_repository"]

    assert isinstance(
        repository,
        SQLiteLearningSessionRepository,
    )

    assert captured["learning_journey"]["domain"] == "英语"

    assert captured["learning_journey"]["goal"] == "6个月达到日常交流"

    assert captured["learning_continuity_context"] is not None


def test_web_continue_should_include_adaptive_planning_in_coach_prompt(
    tmp_path,
    monkeypatch,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "自适应学习测试用户",
            "email": "adaptive-web@example.com",
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

    captured_prompts = []

    def fake_call_llm(system_prompt, user_message):
        captured_prompts.append(system_prompt)

        return {
            "status": "success",
            "content": "今天练习慢速英语听力",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm",
        fake_call_llm,
    )

    journey_url = f"/web/journeys/{journey['journey_id']}"

    # 完成第一节：自评 80。
    first_feedback = client.post(
        f"{journey_url}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "80",
            "difficulty": "听力速度较快",
            "next_step": "练习慢速英语听力",
        },
    )

    assert first_feedback.status_code == 200

    # 继续学习：生成任务，并创建第二节 Session。
    second_continue = client.get(
        f"{journey_url}/continue",
        params={"user_id": user["user_id"]},
    )

    assert second_continue.status_code == 200

    # 完成第二节：自评降至 60。
    second_feedback = client.post(
        f"{journey_url}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "60",
            "difficulty": "语速太快，跟不上",
            "next_step": "先练习慢速英语听力",
        },
    )

    assert second_feedback.status_code == 200

    # 再次继续学习：此时应读取两次已完成的记录。
    third_continue = client.get(
        f"{journey_url}/continue",
        params={"user_id": user["user_id"]},
    )

    assert third_continue.status_code == 200
    assert captured_prompts

    coach_prompt = captured_prompts[-1]

    assert "declining" in coach_prompt
    assert "语速太快，跟不上" in coach_prompt
    assert "先练习慢速英语听力" in coach_prompt
    assert "教学调整建议" in coach_prompt
    assert "适当减小单次任务量" in coach_prompt

    assert "今天练习慢速英语听力" in third_continue.text
