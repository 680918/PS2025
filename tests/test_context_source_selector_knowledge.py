from agent.context.source_selector import (
    select_context_sources,
)


def test_selector_should_choose_memory_and_knowledge_for_personal_review():

    sources = select_context_sources("帮我复习之前整理的Memory Retrieval教程")

    assert "memory" in sources

    assert "knowledge" in sources
