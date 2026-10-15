from agent.controller import run_agent_runtime


def test_runtime_should_detect_context_conflicts():

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

    print("PROJECTED:", state.projected_contexts)
    print("CONFLICTS:", state.context_conflicts)

    assert "learning.current_topic" in state.context_conflicts
