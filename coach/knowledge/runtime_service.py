from coach.knowledge.runtime import (
    detect_knowledge_candidate,
)

from coach.knowledge.suggestion_service import (
    KnowledgeSuggestionService,
)


class KnowledgeRuntimeService:
    def __init__(
        self,
        suggestion_service=None,
    ):

        self.suggestion_service = suggestion_service or KnowledgeSuggestionService()

    def process(
        self,
        state,
    ):

        context = state.learning_continuity_context

        if context is None:
            return None

        candidate = detect_knowledge_candidate(
            {
                "topic": context.get("current_topic"),
                "learning_count": 3,
                "understanding_score": context.get("current_understanding_score") or 0,
            }
        )

        if candidate is None:
            return None

        state.pending_knowledge_candidate = candidate

        suggestion = self.suggestion_service.create_suggestion(candidate)

        state.knowledge_suggestion = suggestion

        return suggestion
