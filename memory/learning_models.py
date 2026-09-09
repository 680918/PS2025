from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class LearningRecord:
    topic: str
    understanding: int
    difficulty: str = ""
    evidence: str = ""
    evidence_type: str = "self_report"
    next_step: str = ""
    source: str = "learning_feedback"

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if not self.topic.strip():
            raise ValueError("topic cannot be empty")

        if not 0 <= self.understanding <= 100:
            raise ValueError("understanding must be between 0 and 100")
