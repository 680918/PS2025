from agent.context_projection import project_learning_continuity
from agent.context_projection import project_learning_memory


def test_project_learning_continuity_should_project_current_topic():
    continuity = {
        "has_current_session": True,
        "current_topic": "Memory",
        "current_understanding_score": None,
        "current_difficulty": None,
        "current_next_step": None,
        "has_previous_session": False,
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts == {
        "learning.current_topic": "Memory",
    }


def test_project_learning_continuity_should_not_project_current_topic_when_no_current_session():
    continuity = {
        "has_current_session": False,
        "current_topic": "Memory",
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts == {}


def test_project_learning_continuity_should_project_previous_topic():
    continuity = {
        "has_current_session": False,
        "has_previous_session": True,
        "topic": "Tool Calling",
        "completed": True,
        "understanding_score": 80,
        "difficulty": "参数结构还不熟",
        "next_step": "继续练习参数结构",
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts["learning.previous_topic"] == "Tool Calling"


def test_project_learning_continuity_should_keep_current_and_previous_topic_separate():
    continuity = {
        "has_current_session": True,
        "current_topic": "Memory",
        "has_previous_session": True,
        "topic": "Tool Calling",
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts == {
        "learning.current_topic": "Memory",
        "learning.previous_topic": "Tool Calling",
    }


def test_project_learning_memory_should_project_completed_domain():
    memory_context = {
        "learning": [
            {
                "memory_key": "journey_completion:python",
                "content": (
                    '{"journey_id": "python", '
                    '"domain": "Python", '
                    '"latest_understanding": 85}'
                ),
            }
        ]
    }

    facts = project_learning_memory(
        memory_context,
    )

    assert facts["learning.completed_domain"] == "Python"


def test_project_learning_memory_should_ignore_invalid_journey_completion_json():
    memory_context = {
        "learning": [
            {
                "memory_key": "journey_completion:broken",
                "content": "not-valid-json",
            }
        ]
    }

    facts = project_learning_memory(
        memory_context,
    )

    assert facts == {}


def test_project_learning_memory_should_project_completed_understanding():
    memory_context = {
        "learning": [
            {
                "memory_key": "journey_completion:python",
                "content": (
                    '{"journey_id": "python", '
                    '"domain": "Python", '
                    '"latest_understanding": 85}'
                ),
            }
        ]
    }

    facts = project_learning_memory(
        memory_context,
    )

    assert facts == {
        "learning.completed_domain": "Python",
        "learning.completed_understanding": 85,
    }


def test_project_learning_memory_should_not_silently_overwrite_multiple_journey_completions():
    memory_context = {
        "learning": [
            {
                "memory_key": "journey_completion:python",
                "content": (
                    '{"journey_id": "python", '
                    '"domain": "Python", '
                    '"latest_understanding": 85}'
                ),
            },
            {
                "memory_key": "journey_completion:english",
                "content": (
                    '{"journey_id": "english", '
                    '"domain": "英语", '
                    '"latest_understanding": 70}'
                ),
            },
        ]
    }

    facts = project_learning_memory(
        memory_context,
    )

    assert facts["learning.completed_journeys"] == [
        {
            "journey_id": "python",
            "domain": "Python",
            "understanding": 85,
        },
        {
            "journey_id": "english",
            "domain": "英语",
            "understanding": 70,
        },
    ]


def test_project_learning_memory_should_not_expose_ambiguous_single_value_fields_for_multiple_journeys():
    memory_context = {
        "learning": [
            {
                "memory_key": "journey_completion:python",
                "content": (
                    '{"journey_id": "python", '
                    '"domain": "Python", '
                    '"latest_understanding": 85}'
                ),
            },
            {
                "memory_key": "journey_completion:english",
                "content": (
                    '{"journey_id": "english", '
                    '"domain": "英语", '
                    '"latest_understanding": 70}'
                ),
            },
        ]
    }

    facts = project_learning_memory(
        memory_context,
    )

    assert "learning.completed_domain" not in facts
    assert "learning.completed_understanding" not in facts
    assert "learning.completed_journeys" in facts


def test_project_learning_continuity_should_project_current_understanding():
    continuity = {
        "has_current_session": True,
        "current_topic": "Memory",
        "current_understanding_score": 75,
        "current_difficulty": None,
        "current_next_step": None,
        "has_previous_session": False,
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts["learning.current_understanding"] == 75


def test_project_learning_continuity_should_project_previous_understanding():
    continuity = {
        "has_current_session": False,
        "has_previous_session": True,
        "topic": "Tool Calling",
        "understanding_score": 80,
        "difficulty": "参数结构还不熟",
        "next_step": "继续练习参数结构",
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts["learning.previous_understanding"] == 80


def test_project_learning_continuity_should_project_current_difficulty():
    continuity = {
        "has_current_session": True,
        "current_topic": "Memory",
        "current_understanding_score": 75,
        "current_difficulty": "长期记忆写入时机还不清楚",
        "current_next_step": None,
        "has_previous_session": False,
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts["learning.current_difficulty"] == "长期记忆写入时机还不清楚"


def test_project_learning_continuity_should_project_previous_difficulty():
    continuity = {
        "has_current_session": False,
        "has_previous_session": True,
        "topic": "Tool Calling",
        "understanding_score": 80,
        "difficulty": "参数结构还不熟",
        "next_step": "继续练习参数结构",
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts["learning.previous_difficulty"] == "参数结构还不熟"


def test_project_learning_continuity_should_project_current_next_step():
    continuity = {
        "has_current_session": True,
        "current_topic": "Memory",
        "current_understanding_score": 75,
        "current_difficulty": "长期记忆写入时机还不清楚",
        "current_next_step": "继续学习长期记忆写入策略",
        "has_previous_session": False,
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts["learning.current_next_step"] == "继续学习长期记忆写入策略"


def test_project_learning_continuity_should_project_previous_next_step():
    continuity = {
        "has_current_session": False,
        "has_previous_session": True,
        "topic": "Tool Calling",
        "understanding_score": 80,
        "difficulty": "参数结构还不熟",
        "next_step": "继续练习参数结构",
    }

    facts = project_learning_continuity(
        continuity,
    )

    assert facts["learning.previous_next_step"] == "继续练习参数结构"
