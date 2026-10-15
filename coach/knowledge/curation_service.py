from coach.knowledge.runtime_adapter import (
    build_curation_context,
)

from coach.knowledge.runtime import (
    detect_knowledge_candidate,
)


def detect_runtime_knowledge_candidate(
    learning_context,
):

    progress, evidences = build_curation_context(learning_context)

    return detect_knowledge_candidate(
        progress,
        evidences,
    )
