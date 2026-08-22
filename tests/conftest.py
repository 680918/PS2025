import pytest


@pytest.fixture
def sample_user_profile():

    return {
        "status": "success",
        "tool_name": "get_user_profile",
        "data": {
            "daily_learning_time": "1小时",
            "learning_preferences": ["原理", "结构", "案例", "实践"],
        },
    }


@pytest.fixture
def sample_skill_map():

    return {
        "status": "success",
        "tool_name": "get_skill_map",
        "data": {"AI Agent": {"level": 90}, "Python": {"level": 15}},
    }
