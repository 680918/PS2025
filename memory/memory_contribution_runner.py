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

            return judge_result["score"]

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
