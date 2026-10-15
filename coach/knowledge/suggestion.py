from dataclasses import dataclass


@dataclass
class KnowledgeSuggestion:
    candidate_id: str

    message: str

    status: str = "PENDING"
