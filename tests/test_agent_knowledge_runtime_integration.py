from coach.knowledge.runtime_service import (
    KnowledgeRuntimeService,
)


def test_runtime_should_attach_knowledge_suggestion():

    state = type("FakeState", (), {})()

    state.learning_continuity_context = {
        "current_topic": "Memory Retrieval",
        "current_understanding_score": 85,
    }

    state.pending_knowledge_candidate = None
    state.knowledge_suggestion = None

    service = KnowledgeRuntimeService()

    service.process(state)

    assert state.pending_knowledge_candidate is not None

    assert state.knowledge_suggestion is not None
