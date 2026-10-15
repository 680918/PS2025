from agent.controller import run_agent_runtime


def test_runtime_should_store_context_evaluation_results():

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

    results = state.context_evaluation_results

    assert "policy_compliance" in results

    assert "trace_completeness" in results
