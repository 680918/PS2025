from llm_client import call_llm

from memory.memory_end_to_end_agent_adapter import (
    run_real_agent_for_memory_evaluation,
)
from memory.memory_end_to_end_evaluator import (
    evaluate_memory_end_to_end_case,
)
from memory.memory_llm_pairwise_judge import (
    judge_memory_contribution_pair,
)


def _summarize_results(
    results,
):
    total_cases = len(results)

    if total_cases == 0:
        return {
            "total_cases": 0,
            "correct_cases": 0,
            "error_cases": 0,
            "accuracy": 0.0,
        }

    correct_cases = sum(1 for result in results if result["is_correct"])

    return {
        "total_cases": total_cases,
        "correct_cases": correct_cases,
        "error_cases": (total_cases - correct_cases),
        "accuracy": (correct_cases / total_cases),
    }


def run_memory_end_to_end_evaluation(
    cases,
    *,
    agent_call=None,
    llm_call=call_llm,
):
    if not cases:
        return {
            "results": [],
            "errors": [],
            "summary": (_summarize_results([])),
        }

    results = []

    for case in cases:

        def agent_runner(
            *,
            query,
            memory_context,
        ):
            return run_real_agent_for_memory_evaluation(
                query=query,
                memory_context=memory_context,
                agent_call=agent_call,
            )

        def pairwise_judge(
            *,
            query,
            without_memory_answer,
            with_memory_answer,
            evaluation_criteria,
            reference_context=None,
        ):
            return judge_memory_contribution_pair(
                query=query,
                without_memory_answer=(without_memory_answer),
                with_memory_answer=(with_memory_answer),
                evaluation_criteria=(evaluation_criteria),
                reference_context=reference_context,
                llm_call=llm_call,
            )

        result = evaluate_memory_end_to_end_case(
            case,
            agent_runner=agent_runner,
            pairwise_judge=pairwise_judge,
        )

        result = {
            **result,
            "category": case.get("category"),
            "domain": case.get("domain"),
            "description": case.get("description"),
        }

        results.append(result)

    errors = [result for result in results if not result["is_correct"]]

    return {
        "results": results,
        "errors": errors,
        "summary": (_summarize_results(results)),
    }
