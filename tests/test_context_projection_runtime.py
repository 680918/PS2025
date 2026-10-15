from agent.controller import run_agent_runtime


def test_runtime_should_store_projected_contexts():

    state, _ = run_agent_runtime(
        user_message="continue learning",
        learning_continuity_context={
            "has_current_session": True,
            "current_topic": "AI Agent",
            "current_understanding_score": 70,
        },
    )

    assert (
        state.projected_contexts["learning_continuity"]["learning.current_topic"]
        == "AI Agent"
    )
