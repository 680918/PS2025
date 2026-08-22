from planning.planner import create_plan, replan_after_failure
from agent.state import AgentState
import pytest

pytestmark = pytest.mark.unit


def test_create_learning_plan_route():

    plan = create_plan("帮我制定未来三个月AI Agent学习计划")

    assert plan["goal"] == "提升AI Agent能力"

    assert len(plan["steps"]) == 3

    assert plan["steps"][0]["tool"] == "get_user_profile"

    assert plan["steps"][1]["tool"] == "get_skill_map"

    assert plan["steps"][2]["tool"] == "create_learning_plan"


def test_create_plan_unknown_task():

    plan = create_plan("今天天气不错")

    assert plan["goal"] == "今天天气不错"

    assert plan["steps"] == []


def test_replan_after_skill_map_failure():

    state = AgentState("帮我制定未来三个月AI Agent学习计划")

    state.add_tool_result(
        "user_profile",
        {
            "status": "success",
            "data": {
                "daily_learning_time": "1小时",
                "learning_preferences": ["原理", "结构", "案例", "实践"],
            },
        },
    )

    new_plan = replan_after_failure(state.user_message, "skill_map", state)

    assert len(new_plan["steps"]) == 1

    assert new_plan["steps"][0]["tool"] == "create_learning_plan"

    assert new_plan["steps"][0]["arguments_from_state"] == ["user_profile"]
