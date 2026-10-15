from agent.context_intelligence_trace import (
    ContextIntelligenceTrace,
)

from agent.context_intelligence_result_builder import (
    build_context_intelligence_result,
)


def test_builder_should_convert_trace_to_result():

    trace = ContextIntelligenceTrace(
        assembled_context="context",
        conflicts={
            "topic": [
                "A",
                "B",
            ]
        },
        resolutions={
            "topic": {
                "source": "conversation",
            }
        },
        evaluations={
            "policy": {},
        },
        report="report",
    )

    result = build_context_intelligence_result(
        trace,
    )

    assert result.context == "context"

    assert "topic" in result.conflicts

    assert result.report == "report"
