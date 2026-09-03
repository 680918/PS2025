from tools.tools import execute_tool
import pytest


pytestmark = pytest.mark.unit


def test_create_learning_plan_full_mode(sample_user_profile, sample_skill_map):

    result = execute_tool(
        "create_learning_plan",
        {"user_profile": sample_user_profile, "skill_map": sample_skill_map},
    )

    assert result["status"] == "success"

    assert result["data"]["mode"] == "full"

    assert result["data"]["focus"] == "加强Python实践"

    assert "month_1" in result["data"]["plan"]
    assert "month_2" in result["data"]["plan"]
    assert "month_3" in result["data"]["plan"]


def test_create_learning_plan_degraded_mode():

    user_profile = {
        "status": "success",
        "tool_name": "get_user_profile",
        "data": {
            "daily_learning_time": "1小时",
            "learning_preferences": ["原理", "结构", "案例", "实践"],
        },
    }

    result = execute_tool("create_learning_plan", {"user_profile": user_profile})

    assert result["status"] == "success"

    assert result["data"]["mode"] == "degraded"

    assert result["data"]["focus"] == "基础学习与实践"

    assert "month_1" in result["data"]["plan"]
    assert "month_2" in result["data"]["plan"]
    assert "month_3" in result["data"]["plan"]


def test_get_memory_default():

    result = execute_tool("get_memory_context")

    assert result["status"] in ["success", "error"]


def test_execute_tool_file_not_found(monkeypatch):

    import tools.tools as tools_module

    def fake_tool():
        raise FileNotFoundError("test file missing")

    monkeypatch.setitem(tools_module.TOOLS, "test_file_not_found", fake_tool)

    result = tools_module.execute_tool("test_file_not_found")

    assert result["status"] == "error"

    assert result["error_type"] == "file_not_found"

    assert result["retryable"] is False

    assert result["replannable"] is True


def test_execute_tool_general_exception(monkeypatch):

    import tools.tools as tools_module

    def fake_tool():
        raise ValueError("bad test data")

    monkeypatch.setitem(tools_module.TOOLS, "test_general_error", fake_tool)

    result = tools_module.execute_tool("test_general_error")

    assert result["status"] == "error"

    assert result["error_type"] == "tool_execution_error"

    assert result["retryable"] is False

    assert result["replannable"] is True


def test_execute_tool_unknown_tool():

    import tools.tools as tools_module

    result = tools_module.execute_tool("tool_that_does_not_exist")

    assert result["status"] == "error"

    assert result["error_type"] == "unknown_tool"

    assert result["retryable"] is False

    assert result["replannable"] is True


def test_load_tool_schemas():

    from tools.tools import load_tool_schemas

    schemas = load_tool_schemas()

    assert isinstance(schemas, list)

    assert len(schemas) > 0

    assert "name" in schemas[0]


def test_filter_tool_schemas():

    from tools.tools import filter_tool_schemas

    result = filter_tool_schemas(["get_user_profile"])

    assert len(result) == 1

    assert result[0]["name"] == "get_user_profile"


def test_filter_tool_schemas_unknown():

    from tools.tools import filter_tool_schemas

    result = filter_tool_schemas(["abc_not_exist"])

    assert result == []


def test_create_learning_plan_high_python_level(sample_user_profile):

    skill_map = {
        "status": "success",
        "tool_name": "get_skill_map",
        "data": {"AI Agent": {"level": 90}, "Python": {"level": 60}},
    }

    result = execute_tool(
        "create_learning_plan",
        {"user_profile": sample_user_profile, "skill_map": skill_map},
    )

    assert result["status"] == "success"

    assert result["data"]["mode"] == "full"

    assert result["data"]["focus"] == "加强AI Agent项目实践"

    assert result["data"]["plan"]["month_1"]["focus"] == "Agent核心模块独立实现"


def test_execute_tool_logs_start_and_success(monkeypatch):
    import tools.tools as tools_module

    def fake_tool():
        return {
            "status": "success",
            "content": "ok",
        }

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

    monkeypatch.setitem(
        tools_module.TOOLS,
        "fake_tool",
        fake_tool,
    )

    monkeypatch.setattr(
        tools_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    result = tools_module.execute_tool(
        "fake_tool",
        run_id="run-123",
    )

    assert result["status"] == "success"

    assert trace_context["run_id"] == "run-123"
    assert len(info_calls) == 2

    start_message, start_args = info_calls[0]

    assert "Tool start" in start_message
    assert "run_id=%s" not in start_message
    assert start_args[0] == "fake_tool"

    success_message, success_args = info_calls[1]

    assert "Tool success" in success_message
    assert "run_id=%s" not in success_message
    assert success_args[0] == "fake_tool"
    assert isinstance(success_args[1], int)


def test_execute_tool_logs_failure(monkeypatch):
    import tools.tools as tools_module

    def fake_tool():
        raise RuntimeError("boom")

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

    monkeypatch.setitem(
        tools_module.TOOLS,
        "fake_tool",
        fake_tool,
    )

    monkeypatch.setattr(
        tools_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    result = tools_module.execute_tool(
        "fake_tool",
        run_id="run-123",
    )

    assert result["status"] == "error"

    assert trace_context["run_id"] == "run-123"
    assert len(error_calls) == 1

    message, args = error_calls[0]

    assert "Tool failed" in message
    assert "run_id=%s" not in message
    assert args[0] == "fake_tool"
    assert args[1] == "tool_execution_error"


def test_execute_tool_logs_unknown_tool(monkeypatch):
    import tools.tools as tools_module

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

    times = iter([30.0, 30.005])

    def fake_perf_counter():
        return next(times)

    monkeypatch.setattr(
        tools_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        tools_module.time,
        "perf_counter",
        fake_perf_counter,
    )

    result = tools_module.execute_tool(
        "not_exists",
        run_id="run-123",
    )

    assert result["status"] == "error"
    assert result["error_type"] == "unknown_tool"

    assert trace_context["run_id"] == "run-123"
    assert len(error_calls) == 1

    message, args = error_calls[0]

    assert "Tool failed" in message
    assert "run_id=%s" not in message
    assert "duration_ms=%s" in message

    assert args[0] == "not_exists"
    assert args[1] == "unknown_tool"
    assert args[2] == 5


def test_execute_tool_logs_success_duration(monkeypatch):
    import tools.tools as tools_module

    def fake_tool():
        return {
            "status": "success",
            "content": "ok",
        }

    info_calls = []

    class FakeTraceLogger:
        def info(self, message, *args):
            info_calls.append((message, args))

        def error(self, message, *args):
            pass

    def fake_get_trace_logger(logger, run_id=None):
        return FakeTraceLogger()

    monkeypatch.setitem(
        tools_module.TOOLS,
        "fake_tool",
        fake_tool,
    )

    monkeypatch.setattr(
        tools_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    result = tools_module.execute_tool("fake_tool")

    assert result["status"] == "success"
    assert len(info_calls) == 2

    message, args = info_calls[1]

    assert "Tool success" in message
    assert "duration_ms=%s" in message
    assert "run_id=%s" not in message

    assert args[0] == "fake_tool"
    assert isinstance(args[1], int)


def test_execute_tool_logs_failure_duration(monkeypatch):
    import tools.tools as tools_module

    error_calls = []

    class FakeTraceLogger:
        def info(self, message, *args):
            pass

        def error(self, message, *args):
            error_calls.append((message, args))

    def fake_get_trace_logger(logger, run_id=None):
        return FakeTraceLogger()

    def fake_tool():
        raise FileNotFoundError("missing file")

    times = iter([20.0, 20.250])

    def fake_perf_counter():
        return next(times)

    monkeypatch.setitem(
        tools_module.TOOLS,
        "fake_tool",
        fake_tool,
    )

    monkeypatch.setattr(
        tools_module,
        "get_trace_logger",
        fake_get_trace_logger,
    )

    monkeypatch.setattr(
        tools_module.time,
        "perf_counter",
        fake_perf_counter,
    )

    result = tools_module.execute_tool(
        "fake_tool",
        run_id="run-123",
    )

    assert result["status"] == "error"
    assert result["error_type"] == "file_not_found"

    assert len(error_calls) == 1

    message, args = error_calls[0]

    assert "Tool failed" in message
    assert "duration_ms=%s" in message
    assert "run_id=%s" not in message

    assert args[0] == "fake_tool"
    assert args[1] == "file_not_found"
    assert args[2] == 250
