from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class LearningEvidence:
    session_id: str
    task: str
    result: str
    assessment: str

    evidence_id: str = field(default_factory=lambda: str(uuid4()))

    tests_passed: int | None = None
    tests_total: int | None = None
