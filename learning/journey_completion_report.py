from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class JourneyCompletionReport:
    journey_id: str
    user_id: str
    summary: dict
    commentary: str

    report_id: str = field(default_factory=lambda: str(uuid4()))
