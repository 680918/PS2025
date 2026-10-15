from coach.knowledge.runtime import (
    detect_knowledge_candidate,
)


def test_runtime_should_detect_candidate():

    candidate = detect_knowledge_candidate(
        {
            "topic": "Memory Retrieval",
            "learning_count": 5,
            "understanding_score": 85,
        }
    )

    assert candidate is not None

    assert candidate.topic == "Memory Retrieval"
