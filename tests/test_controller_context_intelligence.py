from agent.context.source_selector import (
    select_context_sources,
)


def test_context_intelligence_should_record_selected_sources():

    result = select_context_sources("我为什么学不会Python？")

    assert "learning" in result

    assert "memory" in result
