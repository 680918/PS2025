from evaluation.rag_diagnosis import (
    diagnose_rag_case,
    evaluate_retrieval_rank,
)


def test_should_diagnose_retrieval_failure():
    result = diagnose_rag_case(
        retrieved_chunk_ids=[
            "variable-chunk",
        ],
        expected_chunk_id=(
            "function-chunk"
        ),
        answer_passed=False,
    )

    assert result.retrieval_ok is False
    assert (
        result.failure_stage
        == "retrieval"
    )


def test_should_diagnose_generation_or_evaluation_failure():
    result = diagnose_rag_case(
        retrieved_chunk_ids=[
            "function-chunk",
        ],
        expected_chunk_id=(
            "function-chunk"
        ),
        answer_passed=False,
    )

    assert result.retrieval_ok is True
    assert result.answer_ok is False
    assert (
        result.failure_stage
        == "generation_or_evaluation"
    )


def test_should_pass_when_retrieval_and_answer_are_correct():
    result = diagnose_rag_case(
        retrieved_chunk_ids=[
            "function-chunk",
        ],
        expected_chunk_id=(
            "function-chunk"
        ),
        answer_passed=True,
    )

    assert result.retrieval_ok is True
    assert result.answer_ok is True
    assert result.failure_stage is None

def test_should_report_expected_rank():
    class FakeChunk:
        def __init__(self, content):
            self.content = content

    class FakeResult:
        def __init__(self, content):
            self.chunk = FakeChunk(content)

    results = [
        FakeResult("Python变量用于保存数据。"),
        FakeResult("Python循环用于重复执行代码。"),
    ]

    evaluation = evaluate_retrieval_rank(
        results,
        "循环",
    )

    assert evaluation["top1_hit"] is False
    assert evaluation["topk_hit"] is True
    assert evaluation["expected_rank"] == 2

def test_should_report_top1_hit():
    class FakeChunk:
        def __init__(self, content):
            self.content = content

    class FakeResult:
        def __init__(self, content):
            self.chunk = FakeChunk(content)

    results = [
        FakeResult("Python循环用于重复执行代码。"),
        FakeResult("Python变量用于保存数据。"),
    ]

    evaluation = evaluate_retrieval_rank(
        results,
        "循环",
    )

    assert evaluation["top1_hit"] is True
    assert evaluation["topk_hit"] is True
    assert evaluation["expected_rank"] == 1

def test_should_not_match_empty_expected_keyword():
    class FakeChunk:
        def __init__(self, content):
            self.content = content

    class FakeResult:
        def __init__(self, content):
            self.chunk = FakeChunk(content)

    results = [
        FakeResult(
            "Python函数用于封装重复逻辑。"
        ),
    ]

    evaluation = evaluate_retrieval_rank(
        results,
        "",
    )

    assert evaluation["top1_hit"] is False
    assert evaluation["topk_hit"] is False
    assert evaluation["expected_rank"] is None