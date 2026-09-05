from agent.state import AgentState
from agent.controller import (
    decide_failure_action,
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

    def fake_execute_tool(tool_name, arguments=None, run_id=None):

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

    def fake_execute_tool(tool_name, arguments=None, run_id=None):

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

    def fake_execute_tool(tool_name, arguments=None, run_id=None):

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

    def mock_execute_tool(tool_name, arguments=None, run_id=None):

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

    def fake_execute_tool(tool_name, arguments=None, run_id=None):

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
def test_run_simple_agent_without_tool(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm(system_prompt, user_message):

        return {"content": "这是一个简单回答"}

    monkeypatch.setattr(
        controller_module,
        "call_llm",
        fake_call_llm,
    )

    state = controller_module.AgentState("你好")

    result = controller_module.run_simple_agent(
        "你好",
        state=state,
    )

    assert result == "这是一个简单回答"


@pytest.mark.workflow
def test_run_simple_agent_with_tool(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm(system_prompt, user_message):

        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {"content": "<tool_call>get_user_profile</tool_call>"}

        return {"content": "这是根据用户画像生成的回答"}

    monkeypatch.setattr(
        controller_module,
        "call_llm",
        fake_call_llm,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert call_count["llm"] == 2

    assert result == "这是根据用户画像生成的回答"


@pytest.mark.workflow
def test_run_planning_agent_success_output(monkeypatch):

    import agent.controller as controller_module

    def fake_runtime(user_message, state=None):

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

    def fake_runtime(user_message, state=None):

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


def test_run_simple_agent_handles_llm_error(monkeypatch):

    import agent.controller as controller_module

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
        controller_module,
        "call_llm",
        fake_call_llm,
    )

    state = controller_module.AgentState("今天学习什么？")

    result = controller_module.run_simple_agent(
        "今天学习什么？",
        state=state,
    )

    assert isinstance(result, str)
    assert "LLM" in result


@pytest.mark.workflow
def test_run_planning_agent_handles_final_llm_error(monkeypatch):

    import agent.controller as controller_module

    def fake_runtime(user_message, state=None):

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

    def fake_runtime(user_message, state=None):

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


def test_run_simple_agent_retries_retryable_llm_error(monkeypatch):

    import agent.controller as controller_module

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

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller_module.time, "sleep", lambda seconds: None)

    state = controller_module.AgentState("你好")
    result = controller_module.run_simple_agent("你好", state=state)

    assert result == "最终回答"
    assert responses == []


def test_run_simple_agent_does_not_retry_non_retryable_llm_error(monkeypatch):

    import agent.controller as controller_module

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

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)

    state = controller_module.AgentState("你好")
    result = controller_module.run_simple_agent("你好", state=state)

    assert result == "LLM调用失败：Missing DEEPSEEK_API_KEY"
    assert len(calls) == 1


def test_run_simple_agent_retry_fails_returns_error(monkeypatch):

    import agent.controller as controller_module

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

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller_module.time, "sleep", lambda seconds: None)

    state = controller_module.AgentState("你好")
    result = controller_module.run_simple_agent("你好", state=state)

    assert result == "LLM调用失败：timeout"
    assert len(calls) == 2


def test_run_simple_agent_retries_final_llm_after_tool(monkeypatch):

    import agent.controller as controller_module

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

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        return {
            "status": "success",
            "data": {"name": "test user"},
        }

    monkeypatch.setattr(controller_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller_module, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(controller_module.time, "sleep", lambda seconds: None)

    state = controller_module.AgentState("介绍一下我")
    result = controller_module.run_simple_agent("介绍一下我", state=state)

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


def test_call_llm_with_retry_logs_run_id(monkeypatch):
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

    warning_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def warning(self, message, *args):
            warning_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    def fake_call_llm(system_prompt, user_message):
        return responses.pop(0)

    monkeypatch.setattr(
        controller,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        controller,
        "call_llm",
        fake_call_llm,
    )

    monkeypatch.setattr(
        controller.time,
        "sleep",
        lambda seconds: None,
    )

    result = controller.call_llm_with_retry(
        "system",
        "hello",
        run_id="run-123",
    )

    assert result["status"] == "success"

    assert trace_context["run_id"] == "run-123"
    assert len(warning_calls) == 1

    message, args = warning_calls[0]

    assert "LLM retry" in message
    assert "run_id=%s" not in message
    assert args[0] == "llm_timeout"
    assert args[1] == 1


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
        def __init__(self):
            self.run_id = "run-123"

        def get_state(self):
            return {
                "run_id": self.run_id,
                "status": "success",
                "message": "planning completed",
            }

    def fake_runtime(user_message, state=None):
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
        def __init__(self):
            self.run_id = "run-123"

        def get_state(self):
            return {
                "run_id": self.run_id,
                "status": "stop",
                "message": "runtime failed",
            }

    def fake_runtime(user_message, state=None):
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

    class FakeTraceLogger:
        def warning(self, message, *args):
            warning_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        return FakeTraceLogger()

    monkeypatch.setattr(
        controller,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)

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

    class FakeTraceLogger:
        def warning(self, message, *args):
            warning_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        return FakeTraceLogger()

    monkeypatch.setattr(
        controller,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(controller, "call_llm", fake_call_llm)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)

    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)
    monkeypatch.setattr(controller, "LLM_MAX_RETRY_DELAY", 8)

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

    class FakeTraceLogger:
        def warning(self, message, *args):
            pass

        def error(self, message, *args):
            error_calls.append((message, args))

    def fake_get_trace_logger(logger, run_id=None):
        return FakeTraceLogger()

    monkeypatch.setattr(
        controller,
        "get_trace_logger",
        fake_get_trace_logger,
    )

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

    monkeypatch.setattr(controller, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(controller, "LLM_RETRY_DELAY", 1)
    monkeypatch.setattr(controller, "LLM_MAX_RETRY_DELAY", 8)

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


def test_decide_failure_action_logs_retry(monkeypatch):
    import agent.controller as controller

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"

        def can_retry(self):
            return True

        def can_replan(self):
            return True

    state = FakeState()

    result = {
        "status": "error",
        "error_type": "temporary_error",
        "retryable": True,
        "replannable": True,
    }

    warning_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def warning(self, message, *args):
            warning_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    monkeypatch.setattr(
        controller,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    action = controller.decide_failure_action(state, result)

    assert action == "retry"

    assert trace_context["run_id"] == "run-123"
    assert len(warning_calls) == 1

    message, args = warning_calls[0]

    assert "Recovery decision" in message
    assert "run_id=%s" not in message
    assert args[0] == "retry"
    assert args[1] == "temporary_error"


def test_decide_failure_action_logs_replan(monkeypatch):
    import agent.controller as controller

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"

        def can_retry(self):
            return False

        def can_replan(self):
            return True

    state = FakeState()

    result = {
        "status": "error",
        "error_type": "tool_execution_error",
        "retryable": False,
        "replannable": True,
    }

    warning_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def warning(self, message, *args):
            warning_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    monkeypatch.setattr(
        controller,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    action = controller.decide_failure_action(state, result)

    assert action == "replan"
    assert trace_context["run_id"] == "run-123"
    assert len(warning_calls) == 1

    message, args = warning_calls[0]

    assert "Recovery decision" in message
    assert "run_id=%s" not in message
    assert args[0] == "replan"
    assert args[1] == "tool_execution_error"


def test_decide_failure_action_logs_stop(monkeypatch):
    import agent.controller as controller

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"

        def can_retry(self):
            return False

        def can_replan(self):
            return False

    state = FakeState()

    result = {
        "status": "error",
        "error_type": "fatal_error",
        "retryable": False,
        "replannable": False,
    }

    error_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def warning(self, message, *args):
            pass

        def error(self, message, *args):
            error_calls.append((message, args))

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    monkeypatch.setattr(
        controller,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    action = controller.decide_failure_action(state, result)

    assert action == "stop"
    assert trace_context["run_id"] == "run-123"
    assert len(error_calls) == 1

    message, args = error_calls[0]

    assert "Recovery decision" in message
    assert "run_id=%s" not in message
    assert args[0] == "stop"
    assert args[1] == "fatal_error"


def test_runtime_trace_uses_same_run_id_across_layers(monkeypatch):
    import agent.controller as controller_module
    import agent.executor as executor_module

    observed = {
        "executor_run_id": None,
        "tool_run_id": None,
    }

    original_execute_step = executor_module.execute_step

    def fake_execute_step(state, step):
        observed["executor_run_id"] = state.run_id
        return original_execute_step(state, step)

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        observed["tool_run_id"] = run_id

        return {
            "status": "success",
            "content": "ok",
        }

    monkeypatch.setattr(
        executor_module,
        "execute_step",
        fake_execute_step,
    )

    monkeypatch.setattr(
        executor_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("test message")

    step = {
        "step": 1,
        "tool": "fake_tool",
        "arguments": {},
    }

    executor_module.execute_step(state, step)

    assert observed["executor_run_id"] == state.run_id
    assert observed["tool_run_id"] == state.run_id


def test_runtime_trace_run_id_reaches_recovery_log(monkeypatch):
    import agent.controller as controller_module

    state = controller_module.AgentState("test message")

    error_logs = []
    trace_context = {}

    class FakeTraceLogger:
        def warning(self, message, *args):
            pass

        def error(self, message, *args):
            error_logs.append((message, args))

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    monkeypatch.setattr(
        controller_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    result = {
        "status": "error",
        "error_type": "tool_execution_error",
        "retryable": False,
        "replannable": False,
    }

    action = controller_module.decide_failure_action(
        state,
        result,
    )

    assert action == "stop"
    assert trace_context["run_id"] == state.run_id
    assert len(error_logs) == 1

    message, args = error_logs[0]

    assert "Recovery decision" in message
    assert "run_id=%s" not in message
    assert args[0] == "stop"
    assert args[1] == "tool_execution_error"


def test_run_planning_agent_passes_run_id_to_final_llm(monkeypatch):
    import agent.controller as controller

    observed = {}

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"

        def get_state(self):
            return {
                "run_id": self.run_id,
            }

    fake_state = FakeState()

    def fake_run_planning_runtime(user_message, state=None):
        return fake_state, "success"

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        observed["run_id"] = run_id

        return {
            "status": "success",
            "content": "ok",
        }

    monkeypatch.setattr(
        controller,
        "run_planning_runtime",
        fake_run_planning_runtime,
    )

    monkeypatch.setattr(
        controller,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    result = controller.run_planning_agent("hello")

    assert result == "ok"
    assert observed["run_id"] == "run-123"


def test_run_planning_agent_passes_run_id_to_stop_llm(monkeypatch):
    import agent.controller as controller

    observed = {}

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"

        def get_state(self):
            return {
                "run_id": self.run_id,
            }

    fake_state = FakeState()

    def fake_run_planning_runtime(user_message, state=None):
        return fake_state, "stop"

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        observed["run_id"] = run_id

        return {
            "status": "success",
            "content": "failed safely",
        }

    monkeypatch.setattr(
        controller,
        "run_planning_runtime",
        fake_run_planning_runtime,
    )

    monkeypatch.setattr(
        controller,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    result = controller.run_planning_agent("hello")

    assert result == "failed safely"
    assert observed["run_id"] == "run-123"


def test_run_simple_agent_passes_run_id_to_llm(monkeypatch):
    import agent.controller as controller_module

    observed = {}

    monkeypatch.setattr(
        controller_module,
        "route_task",
        lambda user_message: "simple",
    )

    monkeypatch.setattr(
        controller_module,
        "load_tool_schemas",
        lambda: [],
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        observed["run_id"] = run_id

        return {
            "status": "success",
            "content": "hello",
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")
    result = controller_module.run_simple_agent("hello", state=state)

    assert result == "hello"
    assert observed["run_id"] is not None
    assert isinstance(observed["run_id"], str)


def test_run_simple_agent_passes_same_run_id_to_tool(monkeypatch):
    import agent.controller as controller_module

    observed = {
        "llm_run_id": None,
        "tool_run_id": None,
    }

    monkeypatch.setattr(
        controller_module,
        "route_task",
        lambda user_message: "simple",
    )

    monkeypatch.setattr(
        controller_module,
        "load_tool_schemas",
        lambda: [],
    )

    monkeypatch.setattr(
        controller_module,
        "parse_tool_call",
        lambda content: {
            "name": "fake_tool",
            "arguments": {},
        },
    )

    call_count = {"value": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["value"] += 1

        if call_count["value"] == 1:
            observed["llm_run_id"] = run_id

            return {
                "status": "success",
                "content": "tool please",
            }

        return {
            "status": "success",
            "content": "final answer",
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        observed["tool_run_id"] = run_id

        return {
            "status": "success",
            "content": "tool result",
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )
    state = controller_module.AgentState("hello")
    result = controller_module.run_simple_agent("hello", state=state)

    assert result == "final answer"
    assert observed["llm_run_id"] is not None
    assert observed["tool_run_id"] == observed["llm_run_id"]


def test_run_simple_agent_passes_same_run_id_to_final_llm(monkeypatch):
    import agent.controller as controller_module

    observed = {
        "first_llm_run_id": None,
        "final_llm_run_id": None,
    }

    monkeypatch.setattr(
        controller_module,
        "route_task",
        lambda user_message: "simple",
    )

    monkeypatch.setattr(
        controller_module,
        "load_tool_schemas",
        lambda: [],
    )

    monkeypatch.setattr(
        controller_module,
        "parse_tool_call",
        lambda content: {
            "name": "fake_tool",
            "arguments": {},
        },
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        lambda tool_name, arguments=None, run_id=None: {
            "status": "success",
            "content": "tool result",
        },
    )

    call_count = {"value": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["value"] += 1

        if call_count["value"] == 1:
            observed["first_llm_run_id"] = run_id

            return {
                "status": "success",
                "content": "tool please",
            }

        observed["final_llm_run_id"] = run_id

        return {
            "status": "success",
            "content": "final answer",
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )
    state = controller_module.AgentState("hello")
    result = controller_module.run_simple_agent("hello", state=state)

    assert result == "final answer"
    assert observed["first_llm_run_id"] is not None
    assert observed["final_llm_run_id"] == observed["first_llm_run_id"]


def test_run_agent_passes_state_to_planning_agent(monkeypatch):
    import agent.controller as controller

    observed = {}

    monkeypatch.setattr(
        controller,
        "route_task",
        lambda user_message: "planning",
    )

    def fake_run_planning_agent(
        user_message,
        state=None,
    ):
        observed["state"] = state
        return "planning result"

    monkeypatch.setattr(
        controller,
        "run_planning_agent",
        fake_run_planning_agent,
    )

    result = controller.run_agent("hello")

    assert result == "planning result"
    assert observed["state"] is not None
    assert isinstance(observed["state"], controller.AgentState)
    assert observed["state"].user_message == "hello"


def test_run_planning_agent_passes_same_state_to_runtime(monkeypatch):
    import agent.controller as controller

    observed = {}

    state = controller.AgentState("hello")

    def fake_run_planning_runtime(
        user_message,
        state=None,
    ):
        observed["state"] = state
        return state, "success"

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": "ok",
        }

    monkeypatch.setattr(
        controller,
        "run_planning_runtime",
        fake_run_planning_runtime,
    )

    monkeypatch.setattr(
        controller,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    result = controller.run_planning_agent(
        "hello",
        state=state,
    )

    assert result == "ok"
    assert observed["state"] is state


def test_run_planning_runtime_reuses_provided_state(monkeypatch):
    import agent.controller as controller

    state = controller.AgentState("hello")

    monkeypatch.setattr(
        controller,
        "create_plan",
        lambda user_message: {
            "steps": [],
        },
    )

    monkeypatch.setattr(
        controller,
        "execute_plan",
        lambda runtime_state, steps: runtime_state,
    )

    returned_state, runtime_status = controller.run_planning_runtime(
        "hello",
        state=state,
    )

    assert returned_state is state
    assert runtime_status == "success"


def test_run_agent_passes_same_state_to_simple_agent(monkeypatch):
    import agent.controller as controller

    observed = {}

    monkeypatch.setattr(
        controller,
        "route_task",
        lambda user_message: "simple",
    )

    def fake_run_simple_agent(
        user_message,
        state=None,
    ):
        observed["state"] = state
        observed["user_message"] = user_message
        return "simple result"

    monkeypatch.setattr(
        controller,
        "run_simple_agent",
        fake_run_simple_agent,
        raising=False,
    )

    result = controller.run_agent("hello")

    assert result == "simple result"
    assert observed["state"] is not None
    assert isinstance(observed["state"], controller.AgentState)
    assert observed["state"].user_message == "hello"
    assert observed["user_message"] == "hello"


def test_run_simple_agent_stops_when_tool_fails(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["llm"] += 1

        return {
            "status": "success",
            "content": "<tool_call>fake_tool</tool_call>",
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "error",
            "error_type": "tool_error",
            "message": "tool failed",
            "content": None,
            "retryable": False,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert call_count["llm"] == 1
    assert state.last_result["status"] == "error"
    assert state.last_result["error_type"] == "tool_error"
    assert "tool failed" in result


def test_run_simple_agent_records_successful_tool_result(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {
                "status": "success",
                "content": "<tool_call>fake_tool</tool_call>",
            }

        return {
            "status": "success",
            "content": "final answer",
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": {"value": 123},
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert result == "final answer"

    assert state.last_result["status"] == "success"

    assert state.tool_results["fake_tool"]["content"]["value"] == 123


def test_run_simple_agent_records_initial_llm_failure(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "LLM timeout",
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert state.last_result is not None
    assert state.last_result["status"] == "error"
    assert state.last_result["error_type"] == "llm_timeout"
    assert "LLM timeout" in result


def test_run_simple_agent_records_final_llm_failure(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {
                "status": "success",
                "content": "<tool_call>fake_tool</tool_call>",
            }

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "final LLM timeout",
            "retryable": True,
            "replannable": False,
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": {"value": 123},
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert call_count["llm"] == 2
    assert state.last_result is not None
    assert state.last_result["status"] == "error"
    assert state.last_result["error_type"] == "llm_timeout"
    assert "final LLM timeout" in result


def test_run_simple_agent_records_final_llm_success(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {
                "status": "success",
                "content": "<tool_call>fake_tool</tool_call>",
            }

        return {
            "status": "success",
            "content": "final answer",
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": {"value": 123},
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert result == "final answer"
    assert state.last_result is not None
    assert state.last_result["status"] == "success"
    assert state.last_result["content"] == "final answer"


def test_run_simple_agent_records_direct_llm_success(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": "direct answer",
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert result == "direct answer"
    assert state.last_result is not None
    assert state.last_result["status"] == "success"
    assert state.last_result["content"] == "direct answer"


def test_run_simple_agent_sets_success_status_on_direct_answer(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": "direct answer",
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert result == "direct answer"
    assert state.status == "success"


def test_run_simple_agent_sets_stop_status_on_initial_llm_failure(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "LLM timeout",
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert "LLM timeout" in result
    assert state.status == "stop"


def test_run_simple_agent_sets_stop_status_on_tool_failure(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(system_prompt, user_message, run_id=None):
        return {
            "status": "success",
            "content": "<tool_call>fake_tool</tool_call>",
        }

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        return {
            "status": "error",
            "error_type": "tool_error",
            "message": "tool failed",
            "retryable": False,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )
    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert "tool failed" in result
    assert state.status == "stop"


def test_run_simple_agent_sets_stop_status_on_final_llm_failure(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(system_prompt, user_message, run_id=None):
        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {
                "status": "success",
                "content": "<tool_call>fake_tool</tool_call>",
            }

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "final timeout",
            "retryable": True,
            "replannable": False,
        }

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        return {
            "status": "success",
            "content": {"value": 123},
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )
    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert "final timeout" in result
    assert state.status == "stop"


def test_run_simple_agent_sets_success_status_on_final_llm_success(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(system_prompt, user_message, run_id=None):
        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {
                "status": "success",
                "content": "<tool_call>fake_tool</tool_call>",
            }

        return {
            "status": "success",
            "content": "final answer",
        }

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        return {
            "status": "success",
            "content": {"value": 123},
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )
    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    result = controller_module.run_simple_agent(
        "hello",
        state=state,
    )

    assert result == "final answer"
    assert state.status == "success"


def test_run_simple_runtime_returns_state_and_success_status(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": "direct answer",
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")

    runtime_state, runtime_status = controller_module.run_simple_runtime(
        "hello",
        state=state,
    )

    assert runtime_state is state
    assert runtime_status == "success"
    assert runtime_state.last_result["content"] == "direct answer"


def test_run_simple_runtime_returns_state_and_stop_status_on_tool_failure(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": "<tool_call>fake_tool</tool_call>",
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "error",
            "error_type": "tool_error",
            "message": "tool failed",
            "retryable": False,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    runtime_state, runtime_status = controller_module.run_simple_runtime(
        "hello",
        state=state,
    )

    assert runtime_state is state
    assert runtime_status == "stop"
    assert runtime_state.status == "stop"
    assert runtime_state.last_result["status"] == "error"
    assert runtime_state.last_result["error_type"] == "tool_error"


def test_run_simple_runtime_returns_stop_on_initial_llm_failure(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "initial timeout",
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")

    runtime_state, runtime_status = controller_module.run_simple_runtime(
        "hello",
        state=state,
    )

    assert runtime_state is state
    assert runtime_status == "stop"
    assert runtime_state.status == "stop"
    assert runtime_state.last_result["status"] == "error"
    assert runtime_state.last_result["error_type"] == "llm_timeout"


def test_run_simple_runtime_returns_stop_on_final_llm_failure(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {
                "status": "success",
                "content": "<tool_call>fake_tool</tool_call>",
            }

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "final timeout",
            "retryable": True,
            "replannable": False,
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": {"value": 123},
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    runtime_state, runtime_status = controller_module.run_simple_runtime(
        "hello",
        state=state,
    )

    assert runtime_state is state
    assert runtime_status == "stop"
    assert runtime_state.status == "stop"
    assert runtime_state.last_result["status"] == "error"
    assert runtime_state.last_result["error_type"] == "llm_timeout"


def test_run_simple_runtime_records_tool_failure_stage(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": "<tool_call>fake_tool</tool_call>",
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "error",
            "error_type": "tool_timeout",
            "message": "tool timeout",
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    runtime_state, runtime_status = controller_module.run_simple_runtime(
        "hello",
        state=state,
    )

    assert runtime_status == "stop"
    assert runtime_state.failure_stage == "tool"


def test_run_simple_runtime_records_initial_llm_failure_stage(monkeypatch):

    import agent.controller as controller_module

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "initial timeout",
            "retryable": True,
            "replannable": False,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    state = controller_module.AgentState("hello")

    runtime_state, runtime_status = controller_module.run_simple_runtime(
        "hello",
        state=state,
    )

    assert runtime_status == "stop"
    assert runtime_state.failure_stage == "initial_llm"


def test_run_simple_runtime_records_final_llm_failure_stage(monkeypatch):

    import agent.controller as controller_module

    call_count = {"llm": 0}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        call_count["llm"] += 1

        if call_count["llm"] == 1:
            return {
                "status": "success",
                "content": "<tool_call>fake_tool</tool_call>",
            }

        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "final timeout",
            "retryable": True,
            "replannable": False,
        }

    def fake_execute_tool(
        tool_name,
        arguments=None,
        run_id=None,
    ):
        return {
            "status": "success",
            "content": {"value": 123},
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        controller_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = controller_module.AgentState("hello")

    runtime_state, runtime_status = controller_module.run_simple_runtime(
        "hello",
        state=state,
    )

    assert runtime_status == "stop"
    assert runtime_state.failure_stage == "final_llm"


def test_run_agent_simple_path_preserves_runtime_state(monkeypatch):

    import agent.controller as controller_module

    observed = {}

    monkeypatch.setattr(
        controller_module,
        "route_task",
        lambda user_message: "simple",
    )

    def fake_run_simple_agent(user_message, state=None):
        observed["state"] = state

        state.status = "success"
        state.last_result = {
            "status": "success",
            "content": "simple answer",
        }

        return "simple answer"

    monkeypatch.setattr(
        controller_module,
        "run_simple_agent",
        fake_run_simple_agent,
    )

    result = controller_module.run_agent("hello")

    assert result == "simple answer"
    assert observed["state"] is not None
    assert observed["state"].user_message == "hello"
    assert observed["state"].status == "success"
    assert observed["state"].last_result["content"] == "simple answer"
