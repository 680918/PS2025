from learning.journey import LearningJourney
from datetime import datetime


def test_learning_journey_should_store_core_learning_context():
    journey = LearningJourney(
        user_id="user_001",
        domain="AI Agent",
        goal="一年内独立搭建AI智能体",
    )

    assert journey.user_id == "user_001"
    assert journey.domain == "AI Agent"
    assert journey.goal == "一年内独立搭建AI智能体"


def test_learning_journey_should_have_identity_and_status():
    journey = LearningJourney(
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
        journey_id="journey_001",
        status="active",
    )

    assert journey.journey_id == "journey_001"
    assert journey.status == "active"


def test_learning_journey_should_track_timestamps():
    journey = LearningJourney(
        user_id="user_001",
        domain="英语",
        goal="6个月达到日常交流",
    )

    assert isinstance(journey.created_at, datetime)
    assert isinstance(journey.updated_at, datetime)

    assert journey.updated_at >= journey.created_at
