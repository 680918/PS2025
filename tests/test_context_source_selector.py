from agent.context.source_selector import (
    select_context_sources,
)


def test_selector_should_choose_learning_and_memory_for_learning_problem():

    sources = select_context_sources("我为什么学不会Python？")

    assert "learning" in sources

    assert "memory" in sources


def test_selector_should_choose_knowledge_for_general_question():

    sources = select_context_sources("什么是Transformer？")

    assert "knowledge" in sources
