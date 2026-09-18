from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc)


@dataclass
class LearningJourney:
    user_id: str
    domain: str
    goal: str
    journey_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "active"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
