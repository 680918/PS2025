from agent.controller import run_agent_runtime
from agent.context_intelligence_trace import (
    ContextIntelligenceTrace,
)


def test_runtime_should_create_context_intelligence_trace():

    state, _ = run_agent_runtime(
        user_message="continue learning",
        conversation_context=[
            {
                "role": "user",
                "content": "I want to learn Memory",
            }
        ],
        learning_continuity_context={
            "has_current_session": True,
            "current_topic": "Tool Calling",
        },
    )

    assert state.context_intelligence_trace is not None

    assert isinstance(
        state.context_intelligence_trace,
        ContextIntelligenceTrace,
    )

    assert state.context_intelligence_trace.conflicts is not None

    assert state.context_intelligence_trace.report is not None
