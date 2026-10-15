from learning.progress import (
    LearningProgress,
)


def test_learning_progress_should_store_learning_facts():

    progress = LearningProgress(
        topic="Memory Retrieval",
        learning_count=5,
        understanding_score=85,
        completed_tasks=3,
        practice_count=4,
    )

    assert progress.topic == "Memory Retrieval"

    assert progress.learning_count == 5

    assert progress.understanding_score == 85

    assert progress.practice_count == 4
