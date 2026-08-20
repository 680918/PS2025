import pytest

from tools.router import route_tools


pytestmark = pytest.mark.unit


def test_route_tools_learning():

    result = route_tools(
        "我想学习AI Agent"
    )

    assert result == [
        "get_memory_context"
    ]


def test_route_tools_profile():

    result = route_tools(
        "介绍一下我自己"
    )

    assert result == [
        "get_user_profile"
    ]


def test_route_tools_learning_and_profile():

    result = route_tools(
        "介绍一下我的学习情况"
    )

    assert "get_memory_context" in result
    assert "get_user_profile" in result


def test_route_tools_no_match():

    result = route_tools(
        "今天天气不错"
    )

    assert result == []