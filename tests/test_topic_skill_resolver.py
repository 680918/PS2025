from planning.topic_skill_resolver import resolve_skill_from_topic


def test_python_topic_should_resolve_to_python_skill():
    skill = resolve_skill_from_topic("Python函数")

    assert skill == "Python"


def test_unknown_topic_should_return_none():
    skill = resolve_skill_from_topic("未知主题")

    assert skill is None
