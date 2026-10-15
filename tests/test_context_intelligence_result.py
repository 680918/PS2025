from agent.context_intelligence_result import (
    ContextIntelligenceResult,
)


def test_context_intelligence_result_should_store_context_decision():

    result = ContextIntelligenceResult(
        context="context",
        conflicts={
            "learning.current_topic": [
                "Memory",
                "Tool Calling",
            ]
        },
        resolutions={
            "learning.current_topic": {
                "source": "conversation",
                "value": "Memory",
            }
        },
        report="report",
    )

    assert result.context == "context"

    assert "learning.current_topic" in result.conflicts

    assert result.resolutions["learning.current_topic"]["source"] == "conversation"

    assert result.report == "report"
