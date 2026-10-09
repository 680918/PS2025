import json
import memory.context_selector as context_selector

from memory.context_selector import (
    select_relevant_memory_context,
    select_relevant_memory_context_with_budget_diagnostics,
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

    assert selected["learning"][0]["memory_key"] == "journey_completion:python"

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

    assert selected["learning"][0]["memory_key"] == "journey_completion:python"


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

    selected_keys = [memory["memory_key"] for memory in selected["learning"]]

    assert "learning_feedback:001" in selected_keys
    assert "journey_completion:python" in selected_keys
    assert "journey_completion:english" not in selected_keys


def test_memory_context_selector_should_rank_and_limit_learning_memory():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "learning_feedback:english",
                "content": "English vocabulary review",
            },
            {
                "memory_key": "learning_feedback:python",
                "content": "Python Tool Calling practice",
            },
            {
                "memory_key": "learning_feedback:python-basics",
                "content": "Python basics",
            },
        ],
        "project": [],
        "experience": [],
    }

    selected = select_relevant_memory_context(
        memory_context,
        learning_domain="Python",
        query="Python Tool Calling",
        learning_top_k=2,
    )

    selected_keys = [memory["memory_key"] for memory in selected["learning"]]

    assert selected_keys == [
        "learning_feedback:python",
        "learning_feedback:python-basics",
    ]


def test_selector_budget_diagnostics_should_expose_before_and_after_context():
    memory_context = {
        "profile": [
            {
                "memory_key": "profile:one",
                "content": "12345",
            },
            {
                "memory_key": "profile:two",
                "content": "67890",
            },
            {
                "memory_key": "profile:three",
                "content": "abcde",
            },
        ],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context_with_budget_diagnostics(
        memory_context,
        memory_top_k_by_type={
            "profile": 3,
        },
        memory_budget_by_type={
            "profile": 10,
        },
    )

    assert [memory["memory_key"] for memory in result["before_budget"]["profile"]] == [
        "profile:one",
        "profile:two",
        "profile:three",
    ]

    assert [memory["memory_key"] for memory in result["after_budget"]["profile"]] == [
        "profile:one",
        "profile:two",
    ]


def test_selector_budget_diagnostics_after_budget_should_match_regular_selector():
    memory_context = {
        "profile": [
            {
                "memory_key": "profile:one",
                "content": "12345",
            },
            {
                "memory_key": "profile:two",
                "content": "67890",
            },
            {
                "memory_key": "profile:three",
                "content": "abcde",
            },
        ],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    regular_result = select_relevant_memory_context(
        memory_context,
        query="profile",
        memory_top_k_by_type={
            "profile": 3,
        },
        memory_budget_by_type={
            "profile": 10,
        },
    )

    diagnostics_result = select_relevant_memory_context_with_budget_diagnostics(
        memory_context,
        query="profile",
        memory_top_k_by_type={
            "profile": 3,
        },
        memory_budget_by_type={
            "profile": 10,
        },
    )

    assert diagnostics_result["after_budget"] == regular_result


def test_memory_context_selector_should_filter_untrusted_memory_before_ranking(
    monkeypatch,
):
    memory_context = {
        "profile": [
            {
                "memory_key": "profile:false-fact",
                "content": ("False but highly relevant fact."),
                "confidence": 0.0,
            },
            {
                "memory_key": "profile:trusted-fact",
                "content": ("Trusted relevant fact."),
                "confidence": 0.8,
            },
        ],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    captured = {
        "rank_calls": [],
    }

    def fake_rank(
        memories,
        query=None,
    ):
        memory_keys = [memory["memory_key"] for memory in memories]

        captured["rank_calls"].append(memory_keys)

        return memories

    monkeypatch.setattr(
        context_selector,
        "rank_memories_by_composite_score",
        fake_rank,
    )

    selected = select_relevant_memory_context(
        memory_context,
        query="relevant fact",
    )

    assert ["profile:trusted-fact"] in captured["rank_calls"]

    assert all(
        "profile:false-fact" not in memory_keys
        for memory_keys in captured["rank_calls"]
    )

    assert [memory["memory_key"] for memory in selected["profile"]] == [
        "profile:trusted-fact",
    ]


def test_memory_context_selector_should_filter_untrusted_learning_memory():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": ("learning:false-python-mastery"),
                "content": ("The learner has fully mastered Python."),
                "confidence": 0.0,
            },
            {
                "memory_key": ("learning:python-practice"),
                "content": ("The learner still needs Python practice."),
                "confidence": 0.8,
            },
            {
                "memory_key": ("learning:legacy-memory"),
                "content": ("Legacy Python learning memory."),
            },
        ],
        "project": [],
        "experience": [],
    }

    selected = select_relevant_memory_context(
        memory_context,
        query="Continue learning Python",
    )

    selected_keys = [memory["memory_key"] for memory in selected["learning"]]

    assert "learning:false-python-mastery" not in selected_keys

    assert "learning:python-practice" in selected_keys

    assert "learning:legacy-memory" in selected_keys


def test_selector_diagnostics_should_expose_memories_blocked_by_trust():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": ("learning:false-python-mastery"),
                "content": ("The learner has fully mastered Python."),
                "confidence": 0.0,
            },
            {
                "memory_key": ("learning:python-practice"),
                "content": ("The learner still needs Python practice."),
                "confidence": 0.8,
            },
        ],
        "project": [],
        "experience": [],
    }

    diagnostics = select_relevant_memory_context_with_budget_diagnostics(
        memory_context,
        query="Continue learning Python",
    )

    assert [
        memory["memory_key"] for memory in diagnostics["blocked_by_trust"]["learning"]
    ] == [
        "learning:false-python-mastery",
    ]

    assert [
        memory["memory_key"] for memory in diagnostics["after_budget"]["learning"]
    ] == [
        "learning:python-practice",
    ]
