import pytest

from tools.parser import parse_tool_call


pytestmark = pytest.mark.unit


def test_parse_tool_call_no_tag():

    result = parse_tool_call("你好，请直接回答这个问题。")

    assert result is None


def test_parse_tool_call_success():

    result = parse_tool_call("<tool_call>get_user_profile</tool_call>")

    assert result == {"name": "get_user_profile", "arguments": {}}


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

    result = parse_tool_call("<tool_call>get_user_profile")

    assert result is None


def test_parse_tool_call_with_arguments():
    response = """
    <tool_call>
    {
        "name": "save_learning_feedback",
        "arguments": {
            "topic": "Python",
            "understanding": 80,
            "evidence": "测验8/10",
            "evidence_type": "quiz"
        }
    }
    </tool_call>
    """

    result = parse_tool_call(response)

    assert result["name"] == "save_learning_feedback"
    assert result["arguments"]["topic"] == "Python"
    assert result["arguments"]["understanding"] == 80
    assert result["arguments"]["evidence"] == "测验8/10"
    assert result["arguments"]["evidence_type"] == "quiz"


def test_parse_tool_call_keeps_legacy_format_compatible():
    result = parse_tool_call("<tool_call>get_user_profile</tool_call>")

    assert result == {
        "name": "get_user_profile",
        "arguments": {},
    }


def test_parse_tool_call_invalid_json_returns_none():
    response = """
    <tool_call>
    {
        "name": "save_learning_feedback",
        "arguments":
    }
    </tool_call>
    """

    result = parse_tool_call(response)

    assert result is None


def test_parse_tool_call_rejects_non_dict_arguments():
    response = """
    <tool_call>
    {
        "name": "save_learning_feedback",
        "arguments": "Python"
    }
    </tool_call>
    """

    result = parse_tool_call(response)

    assert result is None
