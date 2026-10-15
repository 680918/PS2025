from coach.knowledge.suggestion import (
    KnowledgeSuggestion,
)


def test_knowledge_suggestion_should_store_candidate_information():

    suggestion = KnowledgeSuggestion(
        candidate_id="candidate-001",
        message="是否帮你整理 Memory Retrieval 教程？",
    )

    assert suggestion.candidate_id == "candidate-001"

    assert suggestion.message == "是否帮你整理 Memory Retrieval 教程？"

    assert suggestion.status == "PENDING"
