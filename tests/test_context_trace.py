from agent.context_trace import ContextDecisionTrace


def test_context_decision_trace_should_store_resolution_information():

    trace = ContextDecisionTrace(
        field_name="learning.completed_understanding",
        selected_source="memory",
        selected_value=85,
        reason="field_policy",
        policy="COMPLETED_LEARNING_POLICY",
    )

    assert trace.field_name == ("learning.completed_understanding")

    assert trace.selected_source == "memory"

    assert trace.policy == ("COMPLETED_LEARNING_POLICY")
