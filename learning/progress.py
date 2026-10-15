from dataclasses import dataclass


@dataclass
class LearningProgress:
    topic: str

    learning_count: int

    understanding_score: int

    completed_tasks: int

    practice_count: int
