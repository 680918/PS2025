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
    import agent.executor as executor_module

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"
            self.tool_results = {}
            self.last_result = None
            self.current_step = 0

        def add_tool_result(self, key, result):
            self.tool_results[key] = result

    info_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def info(self, message, *args):
            info_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        return {
            "status": "success",
            "content": "ok",
        }

    monkeypatch.setattr(
        executor_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        executor_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = FakeState()

    step = {
        "step": 1,
        "tool": "fake_tool",
        "arguments": {},
    }

    executor_module.execute_step(state, step)

    assert trace_context["run_id"] == "run-123"

    message, args = info_calls[0]

    assert "Step start" in message
    assert "run_id=%s" not in message
    assert args[0] == 1
    assert args[1] == "fake_tool"


def test_execute_step_logs_success(monkeypatch):
    import agent.executor as executor_module

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"
            self.tool_results = {}
            self.last_result = None
            self.current_step = 0

        def add_tool_result(self, key, result):
            self.tool_results[key] = result

    info_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def info(self, message, *args):
            info_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        return {
            "status": "success",
            "content": "ok",
        }

    monkeypatch.setattr(
        executor_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        executor_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = FakeState()

    step = {
        "step": 1,
        "tool": "fake_tool",
        "arguments": {},
    }

    executor_module.execute_step(state, step)

    assert trace_context["run_id"] == "run-123"

    message, args = info_calls[-1]

    assert "Step success" in message
    assert "run_id=%s" not in message
    assert args[0] == 1
    assert args[1] == "fake_tool"


def test_execute_step_logs_failure(monkeypatch):
    import agent.executor as executor_module

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"
            self.tool_results = {}
            self.last_result = None
            self.current_step = 0

        def add_tool_result(self, key, result):
            self.tool_results[key] = result

    error_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def info(self, message, *args):
            pass

        def error(self, message, *args):
            error_calls.append((message, args))

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        return {
            "status": "error",
            "error_type": "tool_execution_error",
            "message": "failed",
            "retryable": False,
            "replannable": True,
        }

    monkeypatch.setattr(
        executor_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        executor_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = FakeState()

    step = {
        "step": 1,
        "tool": "fake_tool",
        "arguments": {},
    }

    executor_module.execute_step(state, step)

    assert trace_context["run_id"] == "run-123"

    message, args = error_calls[-1]

    assert "Step failed" in message
    assert "run_id=%s" not in message
    assert args[0] == 1
    assert args[1] == "fake_tool"
    assert args[2] == "tool_execution_error"


def test_execute_plan_logs_start(monkeypatch):
    import agent.executor as executor_module

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"
            self.last_result = None
            self.current_step = 0

    info_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def info(self, message, *args):
            info_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    def fake_execute_step(state, step):
        state.last_result = {
            "status": "success",
            "content": "ok",
        }
        return state

    monkeypatch.setattr(
        executor_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        executor_module,
        "execute_step",
        fake_execute_step,
    )

    state = FakeState()

    plan = [
        {
            "step": 1,
            "tool": "fake_tool",
            "arguments": {},
        }
    ]

    executor_module.execute_plan(state, plan)

    assert trace_context["run_id"] == "run-123"

    message, args = info_calls[0]

    assert "Plan start" in message
    assert "run_id=%s" not in message
    assert args[0] == 1


def test_execute_plan_logs_completed(monkeypatch):
    import agent.executor as executor_module

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"
            self.last_result = None
            self.current_step = 0

    info_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def info(self, message, *args):
            info_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    def fake_execute_step(state, step):
        state.last_result = {
            "status": "success",
            "content": "ok",
        }
        return state

    monkeypatch.setattr(
        executor_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        executor_module,
        "execute_step",
        fake_execute_step,
    )

    state = FakeState()

    plan = [
        {
            "step": 1,
            "tool": "fake_tool",
            "arguments": {},
        }
    ]

    executor_module.execute_plan(state, plan)

    assert trace_context["run_id"] == "run-123"

    message, args = info_calls[-1]

    assert "Plan completed" in message
    assert "run_id=%s" not in message
    assert args[0] == 1


def test_execute_plan_logs_stopped(monkeypatch):
    import agent.executor as executor_module

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"
            self.last_result = None
            self.current_step = 0

    error_calls = []
    trace_context = {}

    class FakeTraceLogger:
        def info(self, message, *args):
            pass

        def error(self, message, *args):
            error_calls.append((message, args))

    def fake_get_trace_logger(logger, run_id=None):
        trace_context["run_id"] = run_id
        return FakeTraceLogger()

    def fake_execute_step(state, step):
        state.last_result = {
            "status": "error",
            "error_type": "tool_execution_error",
            "message": "failed",
            "retryable": False,
            "replannable": True,
        }
        return state

    monkeypatch.setattr(
        executor_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        executor_module,
        "execute_step",
        fake_execute_step,
    )

    state = FakeState()

    plan = [
        {
            "step": 1,
            "tool": "fake_tool",
            "arguments": {},
        }
    ]

    executor_module.execute_plan(state, plan)

    assert trace_context["run_id"] == "run-123"

    message, args = error_calls[-1]

    assert "Plan stopped" in message
    assert "run_id=%s" not in message
    assert args[0] == 1
    assert args[1] == "tool_execution_error"


def test_execute_step_passes_run_id_to_tool(monkeypatch):
    import agent.executor as executor_module

    class FakeState:
        def __init__(self):
            self.run_id = "run-123"
            self.tool_results = {}
            self.last_result = None
            self.current_step = 0

        def add_tool_result(self, key, result):
            self.tool_results[key] = result

    received = {}

    def fake_execute_tool(tool_name, arguments=None, run_id=None):
        received["tool_name"] = tool_name
        received["arguments"] = arguments
        received["run_id"] = run_id

        return {
            "status": "success",
            "content": "ok",
        }

    monkeypatch.setattr(
        executor_module,
        "execute_tool",
        fake_execute_tool,
    )

    state = FakeState()

    step = {
        "step": 1,
        "tool": "fake_tool",
        "arguments": {},
    }

    executor_module.execute_step(state, step)

    assert received["tool_name"] == "fake_tool"
    assert received["run_id"] == "run-123"
