from coach.context_models import CoachContext
from coach.context_prompt import build_coach_context_prompt


def test_build_coach_context_prompt_should_include_relevant_user_and_learning_context():
    coach_context = CoachContext(
        user_context={
            "user_id": "user-1",
            "name": "Test User",
            "email": "test@example.com",
        },
        learning_context={
            "domain": "AI Agent",
            "goal": "Build commercial AI Agents",
            "status": "active",
        },
        memory_context={
            "learning": [
                {
                    "content": "Tool Calling completed",
                }
            ]
        },
    )

    prompt = build_coach_context_prompt(coach_context)

    assert "Test User" in prompt
    assert "AI Agent" in prompt
    assert "Build commercial AI Agents" in prompt
    assert "active" in prompt


def test_build_coach_context_prompt_should_not_expose_irrelevant_identity_or_memory():
    coach_context = CoachContext(
        user_context={
            "user_id": "user-1",
            "name": "Test User",
            "email": "test@example.com",
        },
        learning_context={
            "domain": "AI Agent",
            "goal": "Build AI Agents",
            "status": "active",
        },
        memory_context={
            "learning": [
                {
                    "content": "SECRET MEMORY MARKER",
                }
            ]
        },
    )

    prompt = build_coach_context_prompt(coach_context)

    assert "user-1" not in prompt
    assert "test@example.com" not in prompt
    assert "SECRET MEMORY MARKER" not in prompt


def test_build_coach_context_prompt_should_return_empty_when_context_missing():
    assert build_coach_context_prompt(None) == ""
