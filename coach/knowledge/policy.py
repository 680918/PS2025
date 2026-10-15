from dataclasses import dataclass


@dataclass
class KnowledgeCurationPolicy:
    min_learning_count: int = 3

    min_understanding_score: int = 80

    require_completion: bool = False
