from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc)


@dataclass
class ConversationMessage:
    journey_id: str
    user_id: str
    role: str
    content: str
    message_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)
