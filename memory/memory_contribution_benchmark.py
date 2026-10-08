from memory.memory_answer_pair_evaluator import (
    evaluate_memory_answer_pair,
)
from memory.memory_contribution_dataset import (
    get_memory_contribution_evaluation_cases,
)
from memory.memory_contribution_evaluator import (
    evaluate_memory_contribution_results,
)
from memory.memory_rule_quality_scorer import (
    score_answer_with_rules,
    validate_rule_scoring_spec,
)


def _validate_benchmark_answers(
    benchmark_answers,
):
    if not isinstance(
        benchmark_answers,
        dict,
    ):
        raise ValueError("benchmark_answers must be a dict")

    for answer_type in (
        "without_memory",
        "with_memory",
    ):
        answer = benchmark_answers.get(answer_type)

        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(
                f"{answer_type} benchmark answer must be a non-empty string"
            )

    return True


def _evaluate_benchmark_case(
    case,
):
    benchmark_answers = case.get("benchmark_answers")

    _validate_benchmark_answers(benchmark_answers)

    rules = case.get("rule_scoring")

    validate_rule_scoring_spec(rules)

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return benchmark_answers["with_memory"]

        return benchmark_answers["without_memory"]

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

    return evaluate_memory_answer_pair(
        case,
        answer_provider=answer_provider,
        quality_score_provider=(quality_score_provider),
    )


def run_memory_contribution_benchmark():
    cases = get_memory_contribution_evaluation_cases()

    results = [_evaluate_benchmark_case(case) for case in cases]

    summary = evaluate_memory_contribution_results(results)

    return {
        "results": results,
        "summary": summary,
    }
