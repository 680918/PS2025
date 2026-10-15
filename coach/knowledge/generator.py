from coach.knowledge.artifact import (
    KnowledgeArtifact,
)

from datetime import datetime


class KnowledgeArtifactGenerator:
    def generate(
        self,
        candidate,
        content,
    ):

        return KnowledgeArtifact(
            title=(f"{candidate.topic} 学习教程"),
            artifact_type=(candidate.candidate_type),
            topic=(candidate.topic),
            content=content,
            source_candidate=(candidate.candidate_id),
            created_at=datetime.now(),
        )
