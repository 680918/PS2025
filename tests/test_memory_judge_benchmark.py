from memory.memory_judge_benchmark import (
    create_benchmark_answer_provider,
)


def test_benchmark_answer_provider_should_return_without_and_with_memory_answers():
    case = {
        "benchmark_answers": {
            "without_memory": "baseline answer",
            "with_memory": "memory answer",
        },
    }

    provider = create_benchmark_answer_provider(case)

    assert (
        provider(
            query="query",
            memory_context=[],
        )
        == "baseline answer"
    )

    assert (
        provider(
            query="query",
            memory_context=[
                {
                    "memory_key": "memory",
                    "content": "content",
                },
            ],
        )
        == "memory answer"
    )


def test_benchmark_answer_provider_should_reject_missing_answers():
    case = {}

    try:
        create_benchmark_answer_provider(case)
    except ValueError as exc:
        assert "benchmark_answers" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")
