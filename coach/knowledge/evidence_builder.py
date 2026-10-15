from learning.progress import (
    LearningProgress,
)

from learning.evidence import (
    LearningEvidence,
)


def build_learning_progress(
    data,
):

    return LearningProgress(
        topic=data.get(
            "topic",
            "",
        ),
        learning_count=data.get(
            "learning_count",
            0,
        ),
        understanding_score=data.get(
            "understanding_score",
            0,
        ),
        completed_tasks=data.get(
            "completed_tasks",
            0,
        ),
        practice_count=data.get(
            "practice_count",
            0,
        ),
    )


def build_learning_evidence(
    data,
):

    return LearningEvidence(
        session_id=data.get(
            "session_id",
            "",
        ),
        task=data.get(
            "task",
            "",
        ),
        result=data.get(
            "result",
            "",
        ),
        assessment=data.get(
            "assessment",
            "",
        ),
        tests_passed=data.get(
            "tests_passed",
        ),
        tests_total=data.get(
            "tests_total",
        ),
    )
