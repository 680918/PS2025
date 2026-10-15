from agent.context_assembly import assemble_context
from agent.context_conflict import resolve_projection_conflict


def test_resolution_should_follow_learning_field_policy():

    assembled_context = assemble_context(
        conversation_context={},
        learning_continuity={},
        memory_context={},
    )

    projected_contexts = {
        "conversation": {
            "learning.current_topic": "Memory",
        },
        "learning_continuity": {
            "learning.current_topic": "Tool Calling",
        },
        "memory": {
            "learning.current_topic": "Python",
        },
    }

    result = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="learning.current_topic",
    )

    assert result.source == "conversation"
    assert result.value == "Memory"


def test_resolution_should_follow_completed_learning_policy():

    assembled_context = assemble_context(
        conversation_context={},
        learning_continuity={},
        memory_context={},
    )

    projected_contexts = {
        "conversation": {
            "learning.completed_understanding": 60,
        },
        "memory": {
            "learning.completed_understanding": 90,
        },
    }

    result = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="learning.completed_understanding",
    )

    assert result.source == "memory"
    assert result.value == 90


def test_resolution_should_use_default_policy_for_unknown_field():

    assembled_context = assemble_context(
        conversation_context={},
        learning_continuity={},
        memory_context={},
    )

    projected_contexts = {
        "conversation": {
            "unknown.field": "conversation",
        },
        "memory": {
            "unknown.field": "memory",
        },
    }

    result = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="unknown.field",
    )

    assert result.source == "conversation"
    assert result.value == "conversation"
