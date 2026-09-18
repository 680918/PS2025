from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc)


@dataclass
class LearningSession:
    journey_id: str
    user_id: str
    topic: str
    completed: bool = False
    understanding_score: int | None = None
    difficulty: str | None = None
    next_step: str | None = None
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
