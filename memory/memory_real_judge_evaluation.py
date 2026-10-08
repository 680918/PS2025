from memory.memory_contribution_dataset import (
    get_memory_contribution_evaluation_cases,
)
from memory.memory_judge_benchmark import (
    create_benchmark_answer_provider,
)
from memory.memory_judge_comparison import (
    compare_memory_contribution_judges,
    summarize_judge_comparisons,
)


def run_real_judge_benchmark(
    llm_call,
):
    cases = get_memory_contribution_evaluation_cases()

    comparisons = []

    for case in cases:
        answer_provider = create_benchmark_answer_provider(case)

        report = compare_memory_contribution_judges(
            [case],
            answer_provider=answer_provider,
            llm_call=llm_call,
        )

        comparisons.extend(report["comparisons"])

    return {
        "comparisons": comparisons,
        "summary": summarize_judge_comparisons(comparisons),
    }
