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


def test_execute_step_logs_start(monkeypatch):
    import agent.executor as executor

    class FakeState:
        def __init__(self):
            self.last_result = None
            self.current_step = None
            self.tool_results = {}

        def add_tool_result(self, key, result):
            self.tool_results[key] = result

    state = FakeState()

    step = {
        "step": 1,
        "tool": "fake_tool",
        "save_as": "result",
    }

    def fake_resolve_arguments(state, step):
        return {}

    def fake_execute_tool(tool_name, arguments):
        return {
            "status": "success",
            "content": "ok",
        }

    info_calls = []

    def fake_info(message, *args):
        info_calls.append((message, args))

    monkeypatch.setattr(
        executor,
        "resolve_arguments",
        fake_resolve_arguments,
    )
    monkeypatch.setattr(
        executor,
        "execute_tool",
        fake_execute_tool,
    )
    monkeypatch.setattr(
        executor.logger,
        "info",
        fake_info,
    )

    executor.execute_step(state, step)

    message, args = info_calls[0]

    assert "Step start" in message
    assert args[0] == 1
    assert args[1] == "fake_tool"


def test_execute_step_logs_success(monkeypatch):
    import agent.executor as executor

    class FakeState:
        def __init__(self):
            self.last_result = None
            self.current_step = None
            self.tool_results = {}

        def add_tool_result(self, key, result):
            self.tool_results[key] = result

    state = FakeState()

    step = {
        "step": 1,
        "tool": "fake_tool",
        "save_as": "result",
    }

    def fake_resolve_arguments(state, step):
        return {}

    def fake_execute_tool(tool_name, arguments):
        return {
            "status": "success",
            "content": "ok",
        }

    info_calls = []

    def fake_info(message, *args):
        info_calls.append((message, args))

    monkeypatch.setattr(
        executor,
        "resolve_arguments",
        fake_resolve_arguments,
    )
    monkeypatch.setattr(
        executor,
        "execute_tool",
        fake_execute_tool,
    )
    monkeypatch.setattr(
        executor.logger,
        "info",
        fake_info,
    )

    executor.execute_step(state, step)

    assert len(info_calls) == 2

    message, args = info_calls[1]

    assert "Step success" in message
    assert args[0] == 1
    assert args[1] == "fake_tool"


def test_execute_step_logs_failure(monkeypatch):
    import agent.executor as executor

    class FakeState:
        def __init__(self):
            self.last_result = None
            self.current_step = None
            self.tool_results = {}

        def add_tool_result(self, key, result):
            self.tool_results[key] = result

    state = FakeState()

    step = {
        "step": 1,
        "tool": "fake_tool",
        "save_as": "result",
    }

    def fake_resolve_arguments(state, step):
        return {}

    def fake_execute_tool(tool_name, arguments):
        return {
            "status": "error",
            "error_type": "tool_execution_error",
            "message": "boom",
            "retryable": False,
            "replannable": True,
        }

    error_calls = []

    def fake_error(message, *args):
        error_calls.append((message, args))

    monkeypatch.setattr(
        executor,
        "resolve_arguments",
        fake_resolve_arguments,
    )
    monkeypatch.setattr(
        executor,
        "execute_tool",
        fake_execute_tool,
    )
    monkeypatch.setattr(
        executor.logger,
        "error",
        fake_error,
    )

    executor.execute_step(state, step)

    assert len(error_calls) == 1

    message, args = error_calls[0]

    assert "Step failed" in message
    assert args[0] == 1
    assert args[1] == "fake_tool"
    assert args[2] == "tool_execution_error"


def test_execute_plan_logs_start(monkeypatch):
    import agent.executor as executor

    class FakeState:
        def __init__(self):
            self.last_result = None

    state = FakeState()

    plan = [
        {
            "step": 1,
            "tool": "fake_tool",
        }
    ]

    def fake_execute_step(state, step):
        state.last_result = {
            "status": "success",
        }
        return state

    info_calls = []

    def fake_info(message, *args):
        info_calls.append((message, args))

    monkeypatch.setattr(
        executor,
        "execute_step",
        fake_execute_step,
    )
    monkeypatch.setattr(
        executor.logger,
        "info",
        fake_info,
    )

    executor.execute_plan(state, plan)

    message, args = info_calls[0]

    assert "Plan start" in message
    assert args[0] == 1


def test_execute_plan_logs_completed(monkeypatch):
    import agent.executor as executor

    class FakeState:
        def __init__(self):
            self.last_result = None

    state = FakeState()

    plan = [
        {
            "step": 1,
            "tool": "fake_tool",
        }
    ]

    def fake_execute_step(state, step):
        state.last_result = {
            "status": "success",
        }
        return state

    info_calls = []

    def fake_info(message, *args):
        info_calls.append((message, args))

    monkeypatch.setattr(
        executor,
        "execute_step",
        fake_execute_step,
    )
    monkeypatch.setattr(
        executor.logger,
        "info",
        fake_info,
    )

    executor.execute_plan(state, plan)

    message, args = info_calls[-1]

    assert "Plan completed" in message
    assert args[0] == 1


def test_execute_plan_logs_stopped(monkeypatch):
    import agent.executor as executor

    class FakeState:
        def __init__(self):
            self.last_result = None

    state = FakeState()

    plan = [
        {
            "step": 1,
            "tool": "fake_tool",
        },
        {
            "step": 2,
            "tool": "another_tool",
        },
    ]

    executed_steps = []

    def fake_execute_step(state, step):
        executed_steps.append(step["step"])

        state.last_result = {
            "status": "error",
            "error_type": "tool_execution_error",
        }

        return state

    error_calls = []

    def fake_error(message, *args):
        error_calls.append((message, args))

    monkeypatch.setattr(
        executor,
        "execute_step",
        fake_execute_step,
    )
    monkeypatch.setattr(
        executor.logger,
        "error",
        fake_error,
    )

    executor.execute_plan(state, plan)

    assert executed_steps == [1]
    assert len(error_calls) == 1

    message, args = error_calls[0]

    assert "Plan stopped" in message
    assert args[0] == 1
    assert args[1] == "tool_execution_error"
