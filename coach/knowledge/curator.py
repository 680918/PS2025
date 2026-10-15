from coach.knowledge.candidate import (
    KnowledgeCandidate,
)

from coach.knowledge.policy import (
    KnowledgeCurationPolicy,
)

from datetime import datetime


class KnowledgeCurationEngine:
    def __init__(
        self,
        policy=None,
    ):

        self.policy = policy or KnowledgeCurationPolicy()

    def evaluate(
        self,
        progress,
        evidences=None,
    ):

        evidences = evidences or []

        is_legacy_mode = isinstance(
            progress,
            dict,
        )

        if is_legacy_mode:
            topic = progress.get(
                "topic",
                "",
            )

            learning_count = progress.get(
                "learning_count",
                0,
            )

            understanding_score = progress.get(
                "understanding_score",
                0,
            )

        else:
            topic = progress.topic

            learning_count = progress.learning_count

            understanding_score = progress.understanding_score

        if learning_count < self.policy.min_learning_count:
            return None

        if understanding_score < self.policy.min_understanding_score:
            return None

        has_practice_evidence = any(
            (evidence.tests_passed is not None and evidence.tests_passed > 0)
            for evidence in evidences
        )

        if not is_legacy_mode and not has_practice_evidence:
            return None

        return KnowledgeCandidate(
            topic=topic,
            candidate_type="tutorial",
            reason="达到知识沉淀标准",
            confidence=0.9,
            created_at=datetime.now(),
        )
