def create_benchmark_answer_provider(
    case,
):
    benchmark_answers = case.get("benchmark_answers")

    if not isinstance(
        benchmark_answers,
        dict,
    ):
        raise ValueError("benchmark_answers must be a dict")

    without_memory_answer = benchmark_answers.get("without_memory")

    with_memory_answer = benchmark_answers.get("with_memory")

    for (
        answer_name,
        answer,
    ) in (
        (
            "without_memory",
            without_memory_answer,
        ),
        (
            "with_memory",
            with_memory_answer,
        ),
    ):
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(
                f"{answer_name} benchmark answer must be a non-empty string"
            )

    def answer_provider(
        *,
        query,
        memory_context,
    ):
        if memory_context:
            return with_memory_answer

        return without_memory_answer

    return answer_provider
