from planning.goal_type_resolver import resolve_goal_type


def test_exact_ai_agent_goal():
    result = resolve_goal_type("AI Agent")

    assert result == "AI Agent"


def test_natural_language_ai_agent_goal():
    result = resolve_goal_type("一年内掌握AI Agent应用搭建能力")

    assert result == "AI Agent"


def test_unknown_goal_should_return_none():
    result = resolve_goal_type("学习摄影")

    assert result is None


def test_none_goal_should_return_none():
    result = resolve_goal_type(None)

    assert result is None
