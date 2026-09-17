def compare_agent_evaluations(
    previous,
    current,
    tolerance=1e-9,
):
    goal_alignment_delta = current["goal_alignment"] - previous["goal_alignment"]

    actionability_delta = current["actionability"] - previous["actionability"]

    memory_usage_delta = current["memory_usage"] - previous["memory_usage"]

    knowledge_usage_delta = current["knowledge_usage"] - previous["knowledge_usage"]

    response_policy_delta = current["response_policy"] - previous["response_policy"]

    overall_score_delta = current["overall_score"] - previous["overall_score"]

    if overall_score_delta > tolerance:
        status = "improved"
    elif overall_score_delta < -tolerance:
        status = "regressed"
    else:
        status = "unchanged"

    return {
        "status": status,
        "goal_alignment_delta": goal_alignment_delta,
        "actionability_delta": actionability_delta,
        "memory_usage_delta": memory_usage_delta,
        "knowledge_usage_delta": knowledge_usage_delta,
        "response_policy_delta": response_policy_delta,
        "overall_score_delta": overall_score_delta,
    }
