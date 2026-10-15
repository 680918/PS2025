from agent.context_intelligence_trace import (
    ContextIntelligenceTrace,
)


def test_context_intelligence_trace_should_store_runtime_evidence():

    trace = ContextIntelligenceTrace(
        assembled_context="context",
        conflicts={
            "learning.current_topic": [
                "Memory",
                "Tool Calling",
            ]
        },
        resolutions={
            "learning.current_topic": {
                "source": "conversation",
            }
        },
        evaluations={
            "policy_compliance": {},
        },
        report="report",
    )

    assert trace.assembled_context == "context"

    assert "learning.current_topic" in trace.conflicts

    assert trace.resolutions["learning.current_topic"]["source"] == "conversation"

    assert trace.report == "report"
