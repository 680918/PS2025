from agent.controller import run_agent_runtime


def test_runtime_should_resolve_context_conflict():

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

    resolution = state.context_resolutions["learning.current_topic"]

    assert resolution["source"] == "conversation"
    assert resolution["value"] == "I want to learn Memory"
