import pytest

from memory.memory_end_to_end_agent_adapter import (
    normalize_runtime_memory_context,
    run_real_agent_for_memory_evaluation,
)


def test_normalize_runtime_memory_context_should_group_memories_by_type():
    memory_context = [
        {
            "memory_key": "learning:tool-calling",
            "content": "Needs practical exercises.",
        },
        {
            "memory_key": "profile:study-time",
            "content": "Prefers afternoon study.",
        },
        {
            "memory_key": "project:agent-project",
            "content": "Building an AI coach.",
        },
    ]

    result = normalize_runtime_memory_context(memory_context)

    assert result == {
        "profile": [
            {
                "memory_key": "profile:study-time",
                "content": ("Prefers afternoon study."),
            },
        ],
        "skill": [],
        "learning": [
            {
                "memory_key": ("learning:tool-calling"),
                "content": ("Needs practical exercises."),
            },
        ],
        "project": [
            {
                "memory_key": ("project:agent-project"),
                "content": ("Building an AI coach."),
            },
        ],
        "experience": [],
    }


def test_real_agent_adapter_should_use_memory_service():
    captured = {}

    def fake_agent_call(
        user_message,
        memory_service=None,
        **kwargs,
    ):
        captured["user_message"] = user_message

        captured["memory_context"] = memory_service.get_context()

        return "Continue with a practical Tool Calling exercise."

    answer = run_real_agent_for_memory_evaluation(
        query=("Continue learning Tool Calling"),
        memory_context=[
            {
                "memory_key": ("learning:tool-calling"),
                "content": ("The learner already understands the basics."),
            },
        ],
        agent_call=fake_agent_call,
    )

    assert captured["user_message"] == ("Continue learning Tool Calling")

    assert captured["memory_context"] == {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": ("learning:tool-calling"),
                "content": ("The learner already understands the basics."),
            },
        ],
        "project": [],
        "experience": [],
    }

    assert answer == ("Continue with a practical Tool Calling exercise.")


def test_real_agent_adapter_should_use_same_runtime_path_without_memory():
    captured = {}

    def fake_agent_call(
        user_message,
        memory_service=None,
        **kwargs,
    ):
        captured["memory_context"] = memory_service.get_context()

        return "Answer without memory."

    answer = run_real_agent_for_memory_evaluation(
        query="Explain Python lists",
        memory_context=[],
        agent_call=fake_agent_call,
    )

    assert captured["memory_context"] == {
        "profile": [],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    assert answer == ("Answer without memory.")


def test_normalize_runtime_memory_context_should_reject_unknown_type():
    with pytest.raises(
        ValueError,
        match="unsupported memory type",
    ):
        normalize_runtime_memory_context(
            [
                {
                    "memory_key": ("unknown:test-memory"),
                    "content": "Unknown.",
                },
            ]
        )


def test_real_agent_adapter_should_reject_invalid_agent_response():
    def fake_agent_call(
        user_message,
        memory_service=None,
        **kwargs,
    ):
        return ""

    with pytest.raises(
        ValueError,
        match="agent response must be",
    ):
        run_real_agent_for_memory_evaluation(
            query="Explain Python",
            memory_context=[],
            agent_call=fake_agent_call,
        )
