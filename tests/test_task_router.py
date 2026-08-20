import pytest

from agent.task_router import route_task


pytestmark = pytest.mark.unit

# 同一个测试逻辑，用多组输入分别跑一遍(@pytest.mark.parametrize)。
@pytest.mark.parametrize(
    "user_message",
    [
        "帮我制定AI Agent学习路线",
        "帮我做一个AI Agent学习规划",
        "帮我制定AI Agent学习计划",
        "帮我制定未来三个月AI Agent学习计划",
        "我需要一个长期规划"
    ]
)
def test_route_task_planning(
    user_message
):

    result = route_task(
        user_message
    )

    assert result == "planning"


def test_route_task_simple():

    result = route_task(
        "Tool Calling是什么意思？"
    )

    assert result == "simple"