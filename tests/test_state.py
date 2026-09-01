from agent.state import AgentState
import pytest

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
    from agent.state import AgentState

    state = AgentState("hello")

    assert state.run_id
    assert isinstance(state.run_id, str)


def test_agent_state_run_id_is_unique():
    from agent.state import AgentState

    state1 = AgentState("hello")
    state2 = AgentState("hello")

    assert state1.run_id != state2.run_id


def test_get_state_includes_run_id():
    from agent.state import AgentState

    state = AgentState("hello")

    data = state.get_state()

    assert "run_id" in data
    assert data["run_id"] == state.run_id
