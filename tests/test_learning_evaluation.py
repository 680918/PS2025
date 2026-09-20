from learning.session import LearningSession
from evaluation.journey_evaluator import evaluate_journey_progress


def test_evaluation_should_count_only_completed_sessions():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=60,
            difficulty="听不清基本句子",
            next_step="练习基础英语听力",
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=70,
            difficulty="语速较快",
            next_step="练习慢速英语听力",
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=False,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 2


def test_evaluation_should_calculate_understanding_change():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=60,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=70,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 3
    assert result["first_understanding"] == 60
    assert result["latest_understanding"] == 80
    assert result["understanding_change"] == 20


def test_evaluation_should_not_calculate_change_with_only_one_score():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 1
    assert result["first_understanding"] == 80
    assert result["latest_understanding"] == 80

    # 只有一节，无法比较变化。
    assert result["understanding_change"] is None


def test_evaluation_should_return_zero_when_scores_are_equal():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 2
    assert result["first_understanding"] == 80
    assert result["latest_understanding"] == 80
    assert result["understanding_change"] == 0


def test_evaluation_should_detect_improving_trend():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=60,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=70,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["understanding_change"] == 20
    assert result["trend"] == "improving"


def test_evaluation_should_detect_stable_trend():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 2
    assert result["understanding_change"] == 0
    assert result["trend"] == "stable"


def test_evaluation_should_detect_declining_trend():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=70,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=60,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 3
    assert result["first_understanding"] == 80
    assert result["latest_understanding"] == 60
    assert result["understanding_change"] == -20
    assert result["trend"] == "declining"


def test_evaluation_should_detect_insufficient_data():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=True,
            understanding_score=80,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 1
    assert result["first_understanding"] == 80
    assert result["latest_understanding"] == 80
    assert result["understanding_change"] is None
    assert result["trend"] == "insufficient_data"


def test_evaluation_should_handle_empty_session_history():
    result = evaluate_journey_progress(
        sessions=[],
    )

    assert result["completed_sessions"] == 0
    assert result["first_understanding"] is None
    assert result["latest_understanding"] is None
    assert result["understanding_change"] is None
    assert result["trend"] == "insufficient_data"


def test_evaluation_should_ignore_all_uncompleted_sessions():
    sessions = [
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语基础",
            completed=False,
        ),
        LearningSession(
            journey_id="journey-001",
            user_id="user-001",
            topic="英语听力",
            completed=False,
            understanding_score=90,
        ),
    ]

    result = evaluate_journey_progress(
        sessions=sessions,
    )

    assert result["completed_sessions"] == 0
    assert result["first_understanding"] is None
    assert result["latest_understanding"] is None
    assert result["understanding_change"] is None
    assert result["trend"] == "insufficient_data"
