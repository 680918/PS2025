from agent.controller import run_agent_runtime


def test_runtime_should_store_pending_knowledge_candidate():

    state, _ = run_agent_runtime(
        user_message="continue learning",
        learning_continuity_context={
            "has_current_session": True,
            "current_topic": "Memory Retrieval",
            "current_understanding_score": 90,
        },
    )

    assert state.pending_knowledge_candidate is not None

    assert state.pending_knowledge_candidate.topic == "Memory Retrieval"
