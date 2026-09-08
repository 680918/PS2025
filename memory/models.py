from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


ALLOWED_MEMORY_TYPES = {
    "profile",
    "skill",
    "learning",
    "project",
    "experience",
}


@dataclass
class MemoryRecord:
    memory_type: str
    content: str
    importance: float
    confidence: float
    source: str
    memory_key: str | None = None
    id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self):
        self.validate()

        now = datetime.now().isoformat()

        if self.id is None:
            self.id = str(uuid4())

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def validate(self):
        if self.memory_type not in ALLOWED_MEMORY_TYPES:
            raise ValueError(
                f"memory_type must be one of: {sorted(ALLOWED_MEMORY_TYPES)}"
            )

        if not 0 <= self.importance <= 1:
            raise ValueError("importance must be between 0 and 1")

        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
