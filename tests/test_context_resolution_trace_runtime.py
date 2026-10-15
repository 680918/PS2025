from agent.controller import run_agent_runtime


def test_runtime_should_generate_context_resolution_trace():

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

    trace = state.context_resolution_trace["learning.current_topic"]

    assert trace["winner"] == "conversation"
    assert trace["value"] == "I want to learn Memory"
