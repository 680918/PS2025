from coach.knowledge.runtime_service import (
    KnowledgeRuntimeService,
)


def test_runtime_service_should_create_suggestion_from_learning_context():

    service = KnowledgeRuntimeService()

    state = type("FakeState", (), {})()

    state.learning_continuity_context = {
        "current_topic": "Memory Retrieval",
        "current_understanding_score": 85,
    }

    state.pending_knowledge_candidate = None

    state.knowledge_suggestion = None

    service.process(state)

    assert state.pending_knowledge_candidate is not None

    assert state.knowledge_suggestion is not None

    assert (
        state.knowledge_suggestion.candidate_id
        == state.pending_knowledge_candidate.candidate_id
    )
