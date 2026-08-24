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


def test_execute_tool_general_exception(monkeypatch):

    import tools.tools as tools_module

    def fake_tool():
        raise ValueError("bad test data")

    monkeypatch.setitem(tools_module.TOOLS, "test_general_error", fake_tool)

    result = tools_module.execute_tool("test_general_error")

    assert result["status"] == "error"

    assert result["error_type"] == "tool_execution_error"

    assert result["retryable"] is False


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
