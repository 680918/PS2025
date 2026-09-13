from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class KnowledgeDocument:
    title: str
    content: str
    source: str
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


@dataclass
class KnowledgeChunk:
    document_id: str
    content: str
    chunk_index: int
    source: str
    id: str = field(default_factory=lambda: str(uuid4()))

@dataclass
class RetrievalResult:
    chunk: KnowledgeChunk
    score: float


@dataclass
class EmbeddedChunk:
    chunk: KnowledgeChunk
    vector: list[float]