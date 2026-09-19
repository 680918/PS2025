import re

from fastapi.testclient import TestClient
from api.app import create_app


def test_web_learning_flow_should_complete_and_restore_feedback(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    # 1. 注册用户
    register_response = client.post(
        "/web/register",
        data={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    )

    assert register_response.status_code == 200
    assert "注册成功" in register_response.text

    user_id_match = re.search(
        r'name="user_id"\s+value="([^"]+)"',
        register_response.text,
    )

    assert user_id_match is not None

    user_id = user_id_match.group(1)

    assert user_id

    # 2. 创建学习目标
    journey_response = client.post(
        "/web/journeys",
        data={
            "user_id": user_id,
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    )

    assert journey_response.status_code == 200
    assert "学习目标创建成功" in journey_response.text
    assert "英语" in journey_response.text
    assert "开始学习" in journey_response.text

    journey_id_match = re.search(
        r'/web/journeys/([^/"]+)/start',
        journey_response.text,
    )

    assert journey_id_match is not None

    journey_id = journey_id_match.group(1)

    assert journey_id

    # 3. 开始学习
    start_response = client.post(f"/web/journeys/{journey_id}/start")

    assert start_response.status_code == 200
    assert "学习已开始" in start_response.text
    assert "继续学习" in start_response.text

    continue_url_match = re.search(
        r'href="([^"]+/continue\?user_id=[^"]+)"',
        start_response.text,
    )

    assert continue_url_match is not None

    continue_url = continue_url_match.group(1)

    assert continue_url
    # 4. 提交学习反馈
    feedback_response = client.post(
        f"/web/journeys/{journey_id}/feedback",
        data={
            "user_id": user_id,
            "understanding_score": "80",
            "difficulty": "听力速度较快",
            "next_step": "练习慢速英语听力",
        },
    )

    assert feedback_response.status_code == 200
    assert "学习反馈已保存" in feedback_response.text

    # 5. 再次继续学习
    continue_response = client.get(continue_url)

    assert continue_response.status_code == 200

    assert "80" in continue_response.text
    assert "听力速度较快" in continue_response.text
    assert "练习慢速英语听力" in continue_response.text
