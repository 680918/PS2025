from coach.knowledge.curator import (
    KnowledgeCurationEngine,
)


def detect_knowledge_candidate(
    progress,
    evidences=None,
):

    engine = KnowledgeCurationEngine()

    return engine.evaluate(
        progress,
        evidences,
    )
