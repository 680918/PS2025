from coach.knowledge.curator import (
    KnowledgeCurationEngine,
)


def test_engine_should_create_candidate_when_conditions_met():

    engine = KnowledgeCurationEngine()

    candidate = engine.evaluate(
        {
            "topic": "Memory Retrieval",
            "learning_count": 5,
            "understanding_score": 85,
        }
    )

    assert candidate is not None

    assert candidate.topic == "Memory Retrieval"


def test_engine_should_not_create_candidate_when_learning_not_enough():

    engine = KnowledgeCurationEngine()

    candidate = engine.evaluate(
        {
            "topic": "Memory Retrieval",
            "learning_count": 1,
            "understanding_score": 85,
        }
    )

    assert candidate is None
