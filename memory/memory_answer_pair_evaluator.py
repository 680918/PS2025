from memory.memory_contribution_dataset import (
    validate_memory_contribution_case,
)
from memory.memory_contribution_evaluator import (
    evaluate_memory_contribution_case,
)


def evaluate_memory_answer_pair(
    case,
    answer_provider,
    quality_score_provider,
):
    validate_memory_contribution_case(case)

    query = case["query"]
    evaluation_criteria = case["evaluation_criteria"]

    without_memory_answer = answer_provider(
        query=query,
        memory_context=[],
    )

    with_memory_answer = answer_provider(
        query=query,
        memory_context=case["memory_context"],
    )

    without_memory_score = quality_score_provider(
        query=query,
        answer=without_memory_answer,
        evaluation_criteria=(evaluation_criteria),
    )

    with_memory_score = quality_score_provider(
        query=query,
        answer=with_memory_answer,
        evaluation_criteria=(evaluation_criteria),
    )

    result = evaluate_memory_contribution_case(
        case,
        without_memory_score=without_memory_score,
        with_memory_score=with_memory_score,
    )

    return {
        **result,
        "without_memory_answer": (without_memory_answer),
        "with_memory_answer": (with_memory_answer),
    }
