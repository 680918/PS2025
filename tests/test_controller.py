from agent.state import AgentState
from agent.controller import (
    decide_failure_action,
    run_agent,
    run_planning_workflow,
    run_planning_runtime,
)
import agent.executor as executor_module
from unittest.mock import Mock
import pytest


@pytest.mark.unit
def test_decide_continue():

    state = AgentState("测试")

    result = {"status": "success"}

    assert decide_failure_action(state, result) == "continue"


@pytest.mark.unit
def test_decide_retry():

    state = AgentState("测试")

    result = {"status": "error", "retryable": True}

    assert decide_failure_action(state, result) == "retry"


@pytest.mark.unit
def test_decide_replan():

    state = AgentState("测试")

    state.record_retry()

    result = {"status": "error", "retryable": True}

    assert decide_failure_action(state, result) == "replan"


@pytest.mark.unit
def test_decide_stop():

    state = AgentState("测试")

    state.record_retry()
    state.record_replan()

    result = {"status": "error", "retryable": True}

    assert decide_failure_action(state, result) == "stop"


@pytest.mark.workflow
def test_run_planning_workflow_success():

    state = run_planning_workflow("帮我制定未来三个月AI Agent学习计划")

    data = state.get_state()

    assert data["current_step"] == 3

    assert "user_profile" in data["tool_results"]

    assert "skill_map" in data["tool_results"]

    assert "create_learning_plan" in data["tool_results"]

    assert data["tool_results"]["create_learning_plan"]["status"] == "success"


@pytest.mark.workflow
def test_run_planning_workflow_failure(monkeypatch):

    original_execute_tool = executor_module.execute_tool

    def fake_execute_tool(tool_name, arguments=None):

        if tool_name == "get_skill_map":
            return {
                "status": "error",
                "error_type": "temporary_read_error",
                "message": "Temporary test failure",
                "retryable": True,
            }

        return original_execute_tool(tool_name, arguments)

    monkeypatch.setattr(executor_module, "execute_tool", fake_execute_tool)

    state = run_planning_workflow("帮我制定未来三个月AI Agent学习计划")

    data = state.get_state()

    assert data["current_step"] == 2

    assert data["tool_results"]["user_profile"]["status"] == "success"

    assert data["tool_results"]["skill_map"]["status"] == "error"

    assert data["tool_results"]["skill_map"]["error_type"] == "temporary_read_error"

    assert "create_learning_plan" not in data["tool_results"]


# 18个测试——Retry失败 → Replan → Degraded Success
@pytest.mark.workflow
def test_runtime_retry_fail_replan_degraded_success(monkeypatch):

    original_execute_tool = executor_module.execute_tool

    call_count = {"get_skill_map": 0}

    def fake_execute_tool(tool_name, arguments=None):

        if tool_name == "get_skill_map":
            call_count["get_skill_map"] += 1

            return {
                "status": "error",
                "error_type": "temporary_read_error",
                "message": "Temporary test failure",
                "retryable": True,
            }

        return original_execute_tool(tool_name, arguments)

    monkeypatch.setattr(executor_module, "execute_tool", fake_execute_tool)

    state, runtime_status = run_planning_runtime("帮我制定未来三个月AI Agent学习计划")

    data = state.get_state()

    assert runtime_status == "success"

    assert call_count["get_skill_map"] == 2

    assert state.retry_count == 1

    assert state.replan_count == 1

    assert data["tool_results"]["skill_map"]["status"] == "error"

    assert data["tool_results"]["create_learning_plan"]["status"] == "success"

    assert data["tool_results"]["create_learning_plan"]["data"]["mode"] == "degraded"


# 19个测试——Retry失败 → Replan → Stop
@pytest.mark.workflow
def test_runtime_retry_fail_replan_fail_stop(monkeypatch):

    original_execute_tool = executor_module.execute_tool

    call_count = {"get_skill_map": 0, "create_learning_plan": 0}

    def fake_execute_tool(tool_name, arguments=None):

        if tool_name == "get_skill_map":
            call_count["get_skill_map"] += 1

            return {
                "status": "error",
                "error_type": "temporary_read_error",
                "message": "Temporary test failure",
                "retryable": True,
            }

        if tool_name == "create_learning_plan":
            call_count["create_learning_plan"] += 1

            return {
                "status": "error",
                "error_type": "tool_execution_error",
                "message": "Learning plan generation failed",
                "retryable": False,
            }

        return original_execute_tool(tool_name, arguments)

    monkeypatch.setattr(executor_module, "execute_tool", fake_execute_tool)

    state, runtime_status = run_planning_runtime("帮我制定未来三个月AI Agent学习计划")

    data = state.get_state()

    assert runtime_status == "stop"

    assert call_count["get_skill_map"] == 2

    assert call_count["create_learning_plan"] == 1

    assert state.retry_count == 1

    assert state.replan_count == 1

    assert data["tool_results"]["skill_map"]["status"] == "error"

    assert data["tool_results"]["create_learning_plan"]["status"] == "error"

    assert state.last_result["status"] == "error"


@pytest.mark.unit
def test_mock_side_effect_learning():

    mock_tool = Mock()

    mock_tool.side_effect = [
        {
            "status": "error",
            "error_type": "temporary_read_error",
            "message": "Temporary test failure",
            "retryable": True,
        },
        {
            "status": "success",
            "tool_name": "get_skill_map",
            "data": {"AI Agent": {"level": 90}, "Python": {"level": 15}},
        },
    ]

    result_1 = mock_tool("get_skill_map")

    result_2 = mock_tool("get_skill_map")

    assert result_1["status"] == "error"

    assert result_2["status"] == "success"

    assert mock_tool.call_count == 2


@pytest.mark.workflow
def test_runtime_retry_success_resume_with_mock(monkeypatch):

    original_execute_tool = executor_module.execute_tool

    skill_map_mock = Mock()

    skill_map_mock.side_effect = [
        {
            "status": "error",
            "error_type": "temporary_read_error",
            "message": "Temporary test failure",
            "retryable": True,
        },
        {
            "status": "success",
            "tool_name": "get_skill_map",
            "data": {"AI Agent": {"level": 90}, "Python": {"level": 15}},
        },
    ]

    def mock_execute_tool(tool_name, arguments=None):

        if tool_name == "get_skill_map":
            return skill_map_mock(tool_name, arguments)

        return original_execute_tool(tool_name, arguments)

    monkeypatch.setattr(executor_module, "execute_tool", mock_execute_tool)

    state, runtime_status = run_planning_runtime("帮我制定未来三个月AI Agent学习计划")

    data = state.get_state()

    assert runtime_status == "success"

    assert skill_map_mock.call_count == 2

    assert data["current_step"] == 3

    assert data["tool_results"]["skill_map"]["status"] == "success"

    assert data["tool_results"]["create_learning_plan"]["status"] == "success"


@pytest.mark.workflow
def test_direct_replan_then_retryable_error_should_stop(monkeypatch):

    original_execute_tool = executor_module.execute_tool

    call_count = {"create_learning_plan": 0}

    def fake_execute_tool(tool_name, arguments=None):

        # 原计划：
        # get_skill_map 发生不可重试错误
        # → Controller 应直接 Replan
        if tool_name == "get_skill_map":
            return {
                "status": "error",
                "error_type": "file_not_found",
                "message": "skill_map missing",
                "retryable": False,
            }

        # Plan V2：
        # create_learning_plan 发生临时错误
        # 第一次失败后应该 Retry
        # Retry 后第二次仍失败
        if tool_name == "create_learning_plan":
            call_count["create_learning_plan"] += 1

            return {
                "status": "error",
                "error_type": "temporary_read_error",
                "message": "temporary learning plan failure",
                "retryable": True,
            }

        return original_execute_tool(tool_name, arguments)

    monkeypatch.setattr(executor_module, "execute_tool", fake_execute_tool)

    state, runtime_status = run_planning_runtime("帮我制定未来三个月AI Agent学习计划")

    assert call_count["create_learning_plan"] == 2

    assert state.retry_count == 1

    assert state.replan_count == 1

    assert state.last_result["status"] == "error"

    assert runtime_status == "stop"


@pytest.mark.workflow
def test_run_agent_simple_without_tool(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm(system_prompt, user_message):

        return {"content": "这是一个简单回答"}

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)

    result = controller_module.run_agent("你好")

    assert result == "这是一个简单回答"


@pytest.mark.workflow
def test_run_agent_simple_with_tool(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm(system_prompt, user_message):

        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {"content": "<tool_call>get_user_profile</tool_call>"}

        return {"content": "这是根据用户画像生成的回答"}

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)

    result = controller_module.run_agent("介绍一下我自己")

    assert call_count["llm"] == 2

    assert result == "这是根据用户画像生成的回答"


@pytest.mark.workflow
def test_run_planning_agent_success_output(monkeypatch):

    import agent.controller as controller_module

    def fake_runtime(user_message):

        state = AgentState(user_message)

        state.last_result = {"status": "success"}

        return state, "success"

    def fake_call_llm(system_prompt, user_message):

        return {"content": "这是正常规划回答"}

    monkeypatch.setattr(controller_module, "run_planning_runtime", fake_runtime)

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)

    result = controller_module.run_planning_agent("帮我制定学习计划")

    assert result == "这是正常规划回答"


@pytest.mark.workflow
def test_run_planning_agent_stop_output(monkeypatch):

    import agent.controller as controller_module

    def fake_runtime(user_message):

        state = AgentState(user_message)

        state.last_result = {
            "status": "error",
            "error_type": "test_error",
            "message": "test failure",
            "retryable": False,
        }

        return state, "stop"

    def fake_call_llm(system_prompt, user_message):

        return {"content": "当前任务无法完成"}

    monkeypatch.setattr(controller_module, "run_planning_runtime", fake_runtime)

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)

    result = controller_module.run_planning_agent("帮我制定学习计划")

    assert result == "当前任务无法完成"


def test_run_agent_handles_llm_error(monkeypatch):

    def fake_call_llm(
        system_prompt,
        user_message,
    ):

        return {
            "status": "error",
            "error_type": "llm_api_error",
            "message": "LLM service unavailable",
            "content": None,
        }

    monkeypatch.setattr(
        "agent.controller.call_llm",
        fake_call_llm,
    )

    result = run_agent("今天学习什么？")

    assert isinstance(result, str)

    assert "LLM" in result


@pytest.mark.workflow
def test_run_planning_agent_handles_final_llm_error(monkeypatch):

    import agent.controller as controller_module

    def fake_runtime(user_message):

        state = AgentState(user_message)

        state.last_result = {"status": "success"}

        return state, "success"

    def fake_call_llm(system_prompt, user_message):

        return {
            "status": "error",
            "error_type": "llm_api_error",
            "message": "LLM final answer failed",
            "content": None,
        }

    monkeypatch.setattr(controller_module, "run_planning_runtime", fake_runtime)

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)

    result = controller_module.run_planning_agent("帮我制定学习计划")

    assert isinstance(result, str)

    assert "LLM" in result


@pytest.mark.workflow
def test_run_planning_agent_handles_stop_llm_error(monkeypatch):

    import agent.controller as controller_module

    def fake_runtime(user_message):

        state = AgentState(user_message)

        state.last_result = {
            "status": "error",
            "error_type": "test_error",
            "message": "runtime failed",
            "retryable": False,
        }

        return state, "stop"

    def fake_call_llm(system_prompt, user_message):

        return {
            "status": "error",
            "error_type": "llm_api_error",
            "message": "LLM stop message failed",
            "content": None,
        }

    monkeypatch.setattr(controller_module, "run_planning_runtime", fake_runtime)

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)

    result = controller_module.run_planning_agent("帮我制定学习计划")

    assert isinstance(result, str)

    assert "LLM" in result


def test_llm_timeout_should_retry():
    state = AgentState("test message")
    result = {
        "status": "error",
        "error_type": "llm_timeout",
        "message": "timeout",
        "retryable": True,
    }

    action = decide_failure_action(state, result)

    assert action == "retry"


def test_missing_api_key_should_stop():
    state = AgentState("test message")

    result = {
        "status": "error",
        "error_type": "missing_api_key",
        "message": "Missing DEEPSEEK_API_KEY",
        "retryable": False,
        "replannable": False,
    }

    action = decide_failure_action(state, result)

    assert action == "stop"


def test_replannable_error_should_replan():
    state = AgentState("test message")

    result = {
        "status": "error",
        "error_type": "tool_execution_error",
        "message": "tool failed",
        "retryable": False,
        "replannable": True,
    }

    action = decide_failure_action(state, result)

    assert action == "replan"


def test_run_agent_retries_retryable_llm_error(monkeypatch):

    import agent.controller as controller

    responses = [
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "最终回答",
        },
    ]

    def fake_call_llm(system_prompt, user_message):
        return responses.pop(0)

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    result = controller.run_agent("你好")

    assert result == "最终回答"
    assert responses == []


def test_run_agent_does_not_retry_non_retryable_llm_error(monkeypatch):

    import agent.controller as controller

    calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)
        return {
            "status": "error",
            "error_type": "missing_api_key",
            "message": "Missing DEEPSEEK_API_KEY",
            "content": None,
            "retryable": False,
            "replannable": False,
        }

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)

    result = controller.run_agent("你好")

    assert result == "LLM调用失败：Missing DEEPSEEK_API_KEY"
    assert len(calls) == 1


def test_run_agent_retry_fails_returns_error(monkeypatch):

    import agent.controller as controller

    calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    result = controller.run_agent("你好")

    assert result == "LLM调用失败：timeout"
    assert len(calls) == 2


def test_run_agent_retries_final_llm_after_tool(monkeypatch):

    import agent.controller as controller

    llm_responses = [
        {
            "status": "success",
            "content": "<tool_call>get_user_profile</tool_call>",
        },
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "最终回答",
        },
    ]

    def fake_call_llm(system_prompt, user_message):
        return llm_responses.pop(0)

    def fake_execute_tool(tool_name, arguments=None):
        return {
            "status": "success",
            "data": {"name": "test user"},
        }

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    result = controller.run_agent("介绍一下我")

    assert result == "最终回答"
    assert llm_responses == []


def test_call_llm_with_retry_retries_once(monkeypatch):

    import agent.controller as controller

    responses = [
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "ok",
        },
    ]

    def fake_call_llm(system_prompt, user_message):
        return responses.pop(0)

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "success"
    assert result["content"] == "ok"
    assert responses == []


def test_call_llm_with_retry_does_not_retry_non_retryable(monkeypatch):

    import agent.controller as controller

    calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)

        return {
            "status": "error",
            "error_type": "missing_api_key",
            "message": "Missing DEEPSEEK_API_KEY",
            "content": None,
            "retryable": False,
            "replannable": False,
        }

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "error"
    assert len(calls) == 1


def test_call_llm_with_retry_respects_max_retries(monkeypatch):

    import agent.controller as controller

    calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "error"
    assert len(calls) == 3


def test_call_llm_with_retry_zero_retries(monkeypatch):

    import agent.controller as controller

    calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 0)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "error"
    assert len(calls) == 1


def test_call_llm_with_retry_waits_before_retry(monkeypatch):

    import agent.controller as controller

    responses = [
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "ok",
        },
    ]

    sleep_calls = []

    def fake_call_llm(system_prompt, user_message):
        return responses.pop(0)

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", fake_sleep)
    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 2)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "success"
    assert sleep_calls == [2]


def test_call_llm_with_retry_uses_exponential_backoff(monkeypatch):

    import agent.controller as controller

    calls = []
    sleep_calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        }

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", fake_sleep)

    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 3)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "error"
    assert len(calls) == 4
    assert sleep_calls == [1, 2, 4]


def test_call_llm_with_retry_caps_backoff_delay(monkeypatch):

    import agent.controller as controller

    calls = []
    sleep_calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        }

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", fake_sleep)

    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 5)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)
    monkeypatch.setattr(controller, "LLM_MAX_RETRY_DELAY", 8)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "error"
    assert len(calls) == 6
    assert sleep_calls == [1, 2, 4, 8, 8]


def test_run_planning_agent_retries_final_llm(monkeypatch):

    import agent.controller as controller

    llm_responses = [
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "最终学习建议",
        },
    ]

    def fake_call_llm(system_prompt, user_message):
        return llm_responses.pop(0)

    class FakeState:
        def get_state(self):
            return {
                "status": "success",
                "message": "planning completed",
            }

    def fake_runtime(user_message):
        return FakeState(), "success"

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller, "run_planning_runtime", fake_runtime)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    result = controller.run_planning_agent("帮我制定学习计划")

    assert result == "最终学习建议"
    assert llm_responses == []


def test_run_planning_agent_retries_stop_message_llm(monkeypatch):

    import agent.controller as controller

    llm_responses = [
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "任务执行失败，请稍后再试",
        },
    ]

    def fake_call_llm(system_prompt, user_message):
        return llm_responses.pop(0)

    class FakeState:
        def get_state(self):
            return {
                "status": "stop",
                "message": "runtime failed",
            }

    def fake_runtime(user_message):
        return FakeState(), "stop"

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller, "run_planning_runtime", fake_runtime)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    result = controller.run_planning_agent("帮我制定学习计划")

    assert result == "任务执行失败，请稍后再试"
    assert llm_responses == []


def test_call_llm_with_retry_logs_retry(monkeypatch):

    import agent.controller as controller

    responses = [
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "ok",
        },
    ]

    def fake_call_llm(system_prompt, user_message):
        return responses.pop(0)

    warning_calls = []

    def fake_warning(message, *args):
        warning_calls.append((message, args))

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)
    monkeypatch.setattr(controller.logger, "warning", fake_warning)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "success"

    assert len(warning_calls) == 1

    message, args = warning_calls[0]

    assert "LLM retry" in message
    assert args[0] == "llm_timeout"
    assert args[1] == 1
    assert args[2] == 1


def test_call_llm_with_retry_logs_retry_number_and_delay(monkeypatch):

    import agent.controller as controller

    responses = [
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        },
        {
            "status": "success",
            "content": "ok",
        },
    ]

    def fake_call_llm(system_prompt, user_message):
        return responses.pop(0)

    warning_calls = []

    def fake_warning(message, *args):
        warning_calls.append((message, args))

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)
    monkeypatch.setattr(controller, "LLM_MAX_RETRY_DELAY", 8)

    monkeypatch.setattr(controller.logger, "warning", fake_warning)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "success"

    assert len(warning_calls) == 2

    first_message, first_args = warning_calls[0]
    second_message, second_args = warning_calls[1]

    assert "LLM retry" in first_message
    assert first_args[0] == "llm_timeout"
    assert first_args[1] == 1
    assert first_args[2] == 1

    assert "LLM retry" in second_message
    assert second_args[0] == "llm_timeout"
    assert second_args[1] == 2
    assert second_args[2] == 2


def test_call_llm_with_retry_logs_exhausted(monkeypatch):

    import agent.controller as controller

    calls = []
    error_calls = []

    def fake_call_llm(system_prompt, user_message):
        calls.append(1)

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "timeout",
            "content": None,
            "retryable": True,
            "replannable": False,
        }

    def fake_error(message, *args):
        error_calls.append((message, args))

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)
    monkeypatch.setattr(controller, "LLM_MAX_RETRY_DELAY", 8)

    monkeypatch.setattr(controller.logger, "error", fake_error)

    result = controller.call_llm_with_retry(
        "system",
        "hello",
    )

    assert result["status"] == "error"
    assert len(calls) == 3

    assert len(error_calls) == 1

    message, args = error_calls[0]

    assert "retry exhausted" in message.lower()
    assert args[0] == "llm_timeout"
    assert args[1] == 2
