from coach.knowledge.suggestion_builder import (
    build_knowledge_suggestion,
)


class KnowledgeSuggestionService:
    def create_suggestion(
        self,
        candidate,
    ):

        return build_knowledge_suggestion(candidate)
