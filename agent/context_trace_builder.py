from agent.context_trace import ContextDecisionTrace


def build_context_decision_trace(
    field_name,
    resolution,
):

    return ContextDecisionTrace(
        field_name=field_name,
        selected_source=resolution.source,
        selected_value=resolution.value,
        reason=resolution.reason,
        policy=resolution.policy,
    )
