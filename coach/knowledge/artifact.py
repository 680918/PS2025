from dataclasses import dataclass
from datetime import datetime


@dataclass
class KnowledgeArtifact:
    title: str

    artifact_type: str

    topic: str

    content: str

    source_candidate: str

    created_at: datetime
