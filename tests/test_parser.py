import pytest

from tools.parser import parse_tool_call


pytestmark = pytest.mark.unit


def test_parse_tool_call_no_tag():

    result = parse_tool_call(
        "你好，请直接回答这个问题。"
    )

    assert result is None


def test_parse_tool_call_success():

    result = parse_tool_call(
        "<tool_call>get_user_profile</tool_call>"
    )

    assert result == {
        "name": "get_user_profile",
        "arguments": {}
    }


def test_parse_tool_call_strips_whitespace():

    result = parse_tool_call(
        """
        <tool_call>
            get_skill_map
        </tool_call>
        """
    )

    assert result["name"] == "get_skill_map"

    assert result["arguments"] == {}


def test_parse_tool_call_missing_closing_tag():

    result = parse_tool_call(
        "<tool_call>get_user_profile"
    )

    assert result is None
  