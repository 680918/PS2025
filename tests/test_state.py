from agent.state import AgentState
import pytest

pytestmark = pytest.mark.unit


def test_retry_limit():

    state = AgentState("测试")           # 创建State

    assert state.can_retry() is True    # 检查：一开始能不能Retry？-是的

    state.record_retry()                # 记录一次Retry

    assert state.can_retry() is False   # 再检查：还能不能Retry？-应该是False


def test_replan_limit():

    state = AgentState("测试")

    assert state.can_replan() is True

    state.record_replan()

    assert state.can_replan() is False

