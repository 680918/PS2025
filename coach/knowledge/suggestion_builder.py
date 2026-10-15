from coach.knowledge.suggestion import (
    KnowledgeSuggestion,
)


def build_knowledge_suggestion(
    candidate,
):

    return KnowledgeSuggestion(
        candidate_id=(candidate.candidate_id),
        message=(f"你已经完成{candidate.topic}相关学习，是否帮你整理成教程？"),
    )
