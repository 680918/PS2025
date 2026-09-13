from planning.goal_skill_path import (
    get_next_skill,
    get_skill_path,
)


def test_get_ai_agent_skill_path():
    skill_path = get_skill_path("AI Agent")

    assert "Python" in skill_path
    assert "Tool Calling" in skill_path
    assert "Memory" in skill_path


def test_python_should_advance_to_tool_calling():
    next_skill = get_next_skill(
        goal="AI Agent",
        current_skill="Python",
    )

    assert next_skill == "Tool Calling"


def test_unknown_goal_should_return_empty_path():
    skill_path = get_skill_path("未知目标")

    assert skill_path == []


def test_last_skill_should_return_none():
    next_skill = get_next_skill(
        goal="AI Agent",
        current_skill="Agent Architecture",
    )

    assert next_skill is None


def test_natural_language_goal_should_use_ai_agent_skill_path():
    next_skill = get_next_skill(
        goal="一年内掌握AI Agent应用搭建能力",
        current_skill="Python",
    )

    assert next_skill == "Tool Calling"
