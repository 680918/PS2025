from coach.knowledge.evidence_builder import (
    build_learning_progress,
    build_learning_evidence,
)


def build_curation_context(
    learning_context,
):

    progress = build_learning_progress(
        learning_context,
    )

    evidence = build_learning_evidence(
        learning_context,
    )

    return (
        progress,
        [
            evidence,
        ],
    )
