from agent.context_trace_builder import (
    build_context_decision_trace,
)

from agent.context_conflict import (
    ContextConflictResolution,
)


def test_builder_should_convert_resolution_to_trace():

    resolution = ContextConflictResolution(
        source="memory",
        value=85,
        reason="field_policy",
        policy="COMPLETED_LEARNING_POLICY",
    )

    trace = build_context_decision_trace(
        field_name=("learning.completed_understanding"),
        resolution=resolution,
    )

    assert trace.field_name == ("learning.completed_understanding")

    assert trace.selected_source == "memory"

    assert trace.policy == ("COMPLETED_LEARNING_POLICY")
