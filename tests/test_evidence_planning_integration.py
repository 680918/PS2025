from fastapi.testclient import TestClient

from api.app import create_app
from learning.evidence import LearningEvidence
from learning.sqlite_evidence_repository import (
    SQLiteLearningEvidenceRepository,
)


def test_web_continue_should_use_real_evidence_in_planning(
    tmp_path,
    monkeypatch,
):
    captured = {}

    def fake_call_llm(system_prompt, user_message):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "今天继续练习 Python 函数",
        }

    # 仅替换外部 LLM，不替换 run_agent 或 Controller。
    monkeypatch.setattr(
        "agent.controller.call_llm",
        fake_call_llm,
    )

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
            "goal": "学会编写 Python 函数",
        },
    ).json()

    start_response = client.post(f"/journeys/{journey['journey_id']}/start")

    assert start_response.status_code == 200

    session_id = start_response.json()["session_id"]

    # 使用网页现有反馈接口完成上一次学习。
    feedback_response = client.post(
        f"/web/journeys/{journey['journey_id']}/feedback",
        data={
            "user_id": user["user_id"],
            "understanding_score": "80",
            "difficulty": "参数边界处理",
            "next_step": "继续练习边界测试",
        },
    )

    assert feedback_response.status_code == 200

    # 向真实 sessions.db 写入两条 Evidence。
    evidence_repository = SQLiteLearningEvidenceRepository(tmp_path / "sessions.db")

    evidence_repository.save(
        LearningEvidence(
            session_id=session_id,
            task="普通 Python 函数",
            result="4 项测试全部通过",
            assessment="已完成",
            tests_passed=4,
            tests_total=4,
        )
    )

    evidence_repository.save(
        LearningEvidence(
            session_id=session_id,
            task="参数边界处理",
            result="4 项测试通过 3 项",
            assessment="掌握",
            tests_passed=3,
            tests_total=4,
        )
    )

    # 通过真实网页路由运行 Agent。
    response = client.get(
        f"/web/journeys/{journey['journey_id']}/continue",
        params={
            "user_id": user["user_id"],
        },
    )

    assert response.status_code == 200

    system_prompt = captured["system_prompt"]

    assert "1/2" in system_prompt
    assert "教学动作：continue" in system_prompt
    assert "继续围绕未完成练习安排任务" in system_prompt
    assert "上一节学习存在证据不足的练习" in system_prompt

    assert "今天继续练习 Python 函数" in response.text
