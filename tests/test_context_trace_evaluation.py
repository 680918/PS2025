from agent.context_assembly import assemble_context
from agent.context_conflict import (
    resolve_projection_conflict,
)
from agent.context_trace_builder import (
    build_context_decision_trace,
)


def test_trace_should_record_learning_policy():

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
    }

    resolution = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="learning.current_topic",
    )

    trace = build_context_decision_trace(
        field_name="learning.current_topic",
        resolution=resolution,
    )

    assert trace.selected_source == "conversation"

    assert trace.policy == "LEARNING_POLICY"

    assert trace.reason == "field_policy"


def test_trace_should_record_completed_learning_policy():

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

    resolution = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="learning.completed_understanding",
    )

    trace = build_context_decision_trace(
        field_name="learning.completed_understanding",
        resolution=resolution,
    )

    assert trace.selected_source == "memory"

    assert trace.selected_value == 90

    assert trace.policy == ("COMPLETED_LEARNING_POLICY")


def test_trace_should_record_default_policy():

    assembled_context = assemble_context(
        conversation_context={},
        learning_continuity={},
        memory_context={},
    )

    projected_contexts = {
        "conversation": {
            "unknown.field": "A",
        },
        "memory": {
            "unknown.field": "B",
        },
    }

    resolution = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="unknown.field",
    )

    trace = build_context_decision_trace(
        field_name="unknown.field",
        resolution=resolution,
    )

    assert trace.selected_source == "conversation"

    assert trace.policy == "DEFAULT_POLICY"
