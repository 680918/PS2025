from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class KnowledgeCandidate:
    topic: str

    candidate_type: str

    reason: str

    confidence: float

    created_at: datetime

    candidate_id: str = field(default_factory=lambda: str(uuid4()))

    status: str = "PENDING"
