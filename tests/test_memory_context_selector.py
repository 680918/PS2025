import json

from memory.context_selector import (
    select_relevant_memory_context,
)


def test_memory_context_selector_should_keep_only_matching_learning_domain():
    memory_context = {
        "profile": [
            {
                "memory_key": "goal",
                "content": "掌握 AI Agent 搭建能力",
            }
        ],
        "skill": [],
        "learning": [
            {
                "memory_key": "journey_completion:python",
                "content": json.dumps(
                    {
                        "journey_id": "python",
                        "domain": "Python",
                        "latest_understanding": 85,
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "memory_key": "journey_completion:english",
                "content": json.dumps(
                    {
                        "journey_id": "english",
                        "domain": "英语",
                        "latest_understanding": 70,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "project": [],
        "experience": [],
    }

    selected = select_relevant_memory_context(
        memory_context,
        learning_domain="Python",
    )

    assert len(selected["learning"]) == 1

    assert (
        selected["learning"][0]["memory_key"]
        == "journey_completion:python"
    )

    assert selected["profile"] == memory_context["profile"]

def test_memory_context_selector_should_ignore_invalid_learning_memory():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "journey_completion:broken",
                "content": "not-valid-json",
            },
            {
                "memory_key": "journey_completion:python",
                "content": json.dumps(
                    {
                        "journey_id": "python",
                        "domain": "Python",
                        "latest_understanding": 85,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "project": [],
        "experience": [],
    }

    selected = select_relevant_memory_context(
        memory_context,
        learning_domain="Python",
    )

    assert len(selected["learning"]) == 1

    assert (
        selected["learning"][0]["memory_key"]
        == "journey_completion:python"
    )

def test_memory_context_selector_should_preserve_non_journey_learning_memory():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "learning_feedback:001",
                "content": "用户需要增加 Python 实践练习",
            },
            {
                "memory_key": "journey_completion:python",
                "content": json.dumps(
                    {
                        "journey_id": "python",
                        "domain": "Python",
                        "latest_understanding": 85,
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "memory_key": "journey_completion:english",
                "content": json.dumps(
                    {
                        "journey_id": "english",
                        "domain": "英语",
                        "latest_understanding": 70,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "project": [],
        "experience": [],
    }

    selected = select_relevant_memory_context(
        memory_context,
        learning_domain="Python",
    )

    selected_keys = [
        memory["memory_key"]
        for memory in selected["learning"]
    ]

    assert "learning_feedback:001" in selected_keys
    assert "journey_completion:python" in selected_keys
    assert "journey_completion:english" not in selected_keys