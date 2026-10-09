from memory.memory_contribution_evaluator import (
    evaluate_memory_contribution_case,
    evaluate_memory_contribution_results,
)
from memory.memory_answer_pair_evaluator import (
    evaluate_memory_answer_pair,
)
from memory.memory_rule_quality_scorer import (
    score_answer_with_rules,
    validate_rule_scoring_spec,
)
from memory.memory_llm_quality_judge import (
    score_answer_with_llm,
)
from memory.memory_llm_pairwise_judge import (
    judge_memory_contribution_pair,
)


def run_memory_contribution_evaluation(
    cases,
    score_provider,
):
    results = []

    for case in cases:
        without_memory_score = score_provider(
            case,
            False,
        )

        with_memory_score = score_provider(
            case,
            True,
        )

        result = evaluate_memory_contribution_case(
            case,
            without_memory_score=without_memory_score,
            with_memory_score=with_memory_score,
        )

        results.append(result)

    summary = evaluate_memory_contribution_results(results)

    return {
        "results": results,
        "summary": summary,
    }


def run_memory_contribution_answer_evaluation(
    cases,
    answer_provider,
    quality_score_provider,
):
    results = []

    for case in cases:
        result = evaluate_memory_answer_pair(
            case,
            answer_provider=answer_provider,
            quality_score_provider=(quality_score_provider),
        )

        results.append(result)

    summary = evaluate_memory_contribution_results(results)

    return {
        "results": results,
        "summary": summary,
    }


def run_memory_contribution_rule_evaluation(
    cases,
    answer_provider,
):
    results = []

    for case in cases:
        rules = case["rule_scoring"]

        validate_rule_scoring_spec(rules)

        def quality_score_provider(
            *,
            query,
            answer,
            evaluation_criteria,
        ):
            return score_answer_with_rules(
                answer,
                rules,
            )

        result = evaluate_memory_answer_pair(
            case,
            answer_provider=answer_provider,
            quality_score_provider=(quality_score_provider),
        )

        results.append(result)

    summary = evaluate_memory_contribution_results(results)

    return {
        "results": results,
        "summary": summary,
    }


def run_memory_contribution_llm_evaluation(
    cases,
    answer_provider,
    llm_call,
):
    results = []

    for case in cases:

        def quality_score_provider(
            *,
            query,
            answer,
            evaluation_criteria,
        ):
            judge_result = score_answer_with_llm(
                query=query,
                answer=answer,
                evaluation_criteria=(evaluation_criteria),
                llm_call=llm_call,
            )

            return judge_result

        result = evaluate_memory_answer_pair(
            case,
            answer_provider=answer_provider,
            quality_score_provider=(quality_score_provider),
        )

        results.append(result)

    summary = evaluate_memory_contribution_results(results)

    return {
        "results": results,
        "summary": summary,
    }


def _summarize_pairwise_results(
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


def run_memory_contribution_pairwise_evaluation(
    cases,
    answer_provider,
    llm_call,
):
    results = []

    for case in cases:
        query = case["query"]

        without_memory_answer = answer_provider(
            query=query,
            memory_context=[],
        )

        with_memory_answer = answer_provider(
            query=query,
            memory_context=case["memory_context"],
        )

        judgment = judge_memory_contribution_pair(
            query=query,
            without_memory_answer=(without_memory_answer),
            with_memory_answer=(with_memory_answer),
            evaluation_criteria=case["evaluation_criteria"],
            reference_context=case.get("reference_context"),
            llm_call=llm_call,
        )

        actual_effect = judgment["effect"]

        result = {
            "case_id": case["case_id"],
            "expected_effect": case["expected_effect"],
            "actual_effect": (actual_effect),
            "is_correct": (actual_effect == case["expected_effect"]),
            "without_memory_answer": (without_memory_answer),
            "with_memory_answer": (with_memory_answer),
            "pairwise_reason": judgment["reason"],
        }

        results.append(result)

    errors = [result for result in results if not result["is_correct"]]

    return {
        "results": results,
        "summary": (_summarize_pairwise_results(results)),
        "errors": errors,
    }
