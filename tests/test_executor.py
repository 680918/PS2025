from agent.state import AgentState
from agent.executor import execute_step, execute_plan
import pytest


pytestmark = pytest.mark.integration


def test_execute_step_success():

    state = AgentState("测试Executor")

    step = {"step": 1, "tool": "get_user_profile", "save_as": "user_profile"}

    state = execute_step(state, step)

    assert state.current_step == 1

    assert state.last_result["status"] == "success"

    assert "user_profile" in state.tool_results


def test_execute_step_failure():

    state = AgentState("测试Executor失败")

    step = {"step": 2, "tool": "abc_not_exist", "save_as": "skill_map"}

    state = execute_step(state, step)

    assert state.current_step == 2

    assert state.last_result["status"] == "error"

    assert state.last_result["error_type"] == "unknown_tool"

    assert "skill_map" in state.tool_results

    assert state.tool_results["skill_map"]["status"] == "error"


def test_execute_plan_stops_on_error():

    state = AgentState("测试Plan遇错暂停")

    plan = [
        {"step": 1, "tool": "get_user_profile", "save_as": "user_profile"},
        {"step": 2, "tool": "abc_not_exist", "save_as": "skill_map"},
        {
            "step": 3,
            "tool": "create_learning_plan",
            "arguments_from_state": ["user_profile", "skill_map"],
        },
    ]

    state = execute_plan(state, plan)

    assert state.current_step == 2

    assert state.last_result["status"] == "error"

    assert "user_profile" in state.tool_results

    assert "skill_map" in state.tool_results

    assert "create_learning_plan" not in state.tool_results
