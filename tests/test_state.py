import pytest

from agent.state import AgentState
from memory.service import MemoryService
from memory.store import MemoryStore

pytestmark = pytest.mark.unit


def test_retry_limit():

    state = AgentState("测试")  # 创建State

    assert state.can_retry() is True  # 检查：一开始能不能Retry？-是的

    state.record_retry()  # 记录一次Retry

    assert state.can_retry() is False  # 再检查：还能不能Retry？-应该是False


def test_replan_limit():

    state = AgentState("测试")

    assert state.can_replan() is True

    state.record_replan()

    assert state.can_replan() is False


def test_agent_state_has_run_id():

    state = AgentState("hello")

    assert state.run_id
    assert isinstance(state.run_id, str)


def test_agent_state_run_id_is_unique():

    state1 = AgentState("hello")
    state2 = AgentState("hello")

    assert state1.run_id != state2.run_id


def test_get_state_includes_run_id():

    state = AgentState("hello")

    data = state.get_state()

    assert "run_id" in data
    assert data["run_id"] == state.run_id


def test_get_state_includes_status():

    state = AgentState("hello")
    state.status = "success"

    result = state.get_state()

    assert result["status"] == "success"


def test_get_state_includes_last_result():

    state = AgentState("hello")

    state.last_result = {
        "status": "error",
        "error_type": "tool_error",
        "message": "tool failed",
    }

    result = state.get_state()

    assert result["last_result"]["status"] == "error"
    assert result["last_result"]["error_type"] == "tool_error"


def test_get_state_includes_failure_stage():

    state = AgentState("hello")
    state.failure_stage = "tool"

    result = state.get_state()

    assert result["failure_stage"] == "tool"


def test_agent_state_stores_memory_context():

    state = AgentState("我今天应该学习什么？")

    memory_context = {
        "skill": [
            {
                "memory_key": "python_skill",
                "content": "用户正在学习 Python",
            }
        ]
    }

    state.set_memory_context(memory_context)

    assert state.memory_context == memory_context
    assert state.get_state()["memory_context"] == memory_context


def test_agent_state_stores_memory_service_dependency():

    store = MemoryStore()
    memory_service = MemoryService(store)

    state = AgentState(
        "测试问题",
        memory_service=memory_service,
    )

    assert state.memory_service is memory_service


def test_memory_service_dependency_is_not_exposed_in_state_data():

    store = MemoryStore()
    memory_service = MemoryService(store)

    state = AgentState(
        "测试问题",
        memory_service=memory_service,
    )

    state_data = state.get_state()

    assert "memory_service" not in state_data


def test_agent_state_should_store_routing_trace():
    state = AgentState("test")

    routing_trace = {
        "selected_document_ids": ["doc-agent"],
        "candidates": [
            {
                "document_id": "doc-agent",
                "score": 4,
                "selected": True,
                "reason": "selected",
            }
        ],
    }

    state.set_routing_trace(routing_trace)

    assert state.routing_trace == routing_trace
    assert state.get_state()["routing_trace"] == routing_trace


def test_agent_state_should_default_routing_trace_to_none():
    state = AgentState("test")

    assert state.routing_trace is None
    assert state.get_state()["routing_trace"] is None
