def _validate_agent_answer(
    answer,
):
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("agent answer must be a non-empty string")

    return answer


def evaluate_memory_end_to_end_case(
    case,
    agent_runner,
    pairwise_judge,
):
    query = case["query"]

    without_memory_answer = _validate_agent_answer(
        agent_runner(
            query=query,
            memory_context=[],
        )
    )

    with_memory_answer = _validate_agent_answer(
        agent_runner(
            query=query,
            memory_context=case["memory_context"],
        )
    )

    judge_kwargs = {
        "query": query,
        "without_memory_answer": (without_memory_answer),
        "with_memory_answer": (with_memory_answer),
        "evaluation_criteria": case["evaluation_criteria"],
    }

    if "reference_context" in case:
        judge_kwargs["reference_context"] = case["reference_context"]

    judgment = pairwise_judge(**judge_kwargs)

    actual_effect = judgment["effect"]

    return {
        "case_id": case["case_id"],
        "expected_effect": case["expected_effect"],
        "actual_effect": (actual_effect),
        "is_correct": (actual_effect == case["expected_effect"]),
        "without_memory_answer": (without_memory_answer),
        "with_memory_answer": (with_memory_answer),
        "pairwise_reason": judgment["reason"],
    }
