import pytest

from knowledge.models import (
    KnowledgeChunk,
    RetrievalResult,
)
from evaluation.retrieval_evaluator import (
    RetrievalEvaluationCase,
    evaluate_retrieval,
    hit_at_k,
)


def make_result(
    chunk_id,
    content,
    score,
):
    chunk = KnowledgeChunk(
        document_id="doc-1",
        content=content,
        chunk_index=0,
        source="test.txt",
        id=chunk_id,
    )

    return RetrievalResult(
        chunk=chunk,
        score=score,
    )


def test_hit_at_1_should_return_true_when_first_result_is_correct():
    results = [
        make_result(
            "correct",
            "Python函数可以封装重复逻辑。",
            5.0,
        ),
        make_result(
            "other",
            "Python变量用于保存数据。",
            2.0,
        ),
    ]

    assert hit_at_k(
        results,
        expected_chunk_id="correct",
        k=1,
    )


def test_hit_at_1_should_return_false_when_correct_result_is_second():
    results = [
        make_result(
            "other",
            "Python变量用于保存数据。",
            5.0,
        ),
        make_result(
            "correct",
            "Python函数可以封装重复逻辑。",
            4.0,
        ),
    ]

    assert not hit_at_k(
        results,
        expected_chunk_id="correct",
        k=1,
    )


def test_hit_at_3_should_find_correct_result():
    results = [
        make_result("a", "变量", 5.0),
        make_result("b", "循环", 4.0),
        make_result(
            "correct",
            "Python函数可以封装重复逻辑。",
            3.0,
        ),
    ]

    assert hit_at_k(
        results,
        expected_chunk_id="correct",
        k=3,
    )


def test_hit_at_k_should_return_false_for_empty_results():
    assert not hit_at_k(
        [],
        expected_chunk_id="correct",
        k=3,
    )


def test_hit_at_k_rejects_invalid_k():
    with pytest.raises(ValueError):
        hit_at_k(
            [],
            expected_chunk_id="correct",
            k=0,
        )


def test_evaluate_real_retriever():
    from knowledge.models import KnowledgeChunk
    from knowledge.retriever import retrieve_chunks
    from knowledge.store import KnowledgeStore

    store = KnowledgeStore()

    function_chunk = KnowledgeChunk(
        document_id="python",
        content="Python函数可以封装重复逻辑并接受参数。",
        chunk_index=0,
        source="python.txt",
        id="function-chunk",
    )

    variable_chunk = KnowledgeChunk(
        document_id="python",
        content="Python变量用于保存程序运行中的数据。",
        chunk_index=1,
        source="python.txt",
        id="variable-chunk",
    )

    loop_chunk = KnowledgeChunk(
        document_id="python",
        content="Python循环可以重复执行一段代码。",
        chunk_index=2,
        source="python.txt",
        id="loop-chunk",
    )

    store.add_many(
        [
            function_chunk,
            variable_chunk,
            loop_chunk,
        ]
    )

    cases = [
        RetrievalEvaluationCase(
            query="Python函数有什么作用？",
            expected_chunk_id="function-chunk",
        ),
        RetrievalEvaluationCase(
            query="Python变量是干什么的？",
            expected_chunk_id="variable-chunk",
        ),
        RetrievalEvaluationCase(
            query="Python循环有什么作用？",
            expected_chunk_id="loop-chunk",
        ),
    ]

    def retriever(query, k):
        return retrieve_chunks(
            query,
            store,
            top_k=k,
        )

    evaluation = evaluate_retrieval(
        retriever,
        cases,
        k=1,
    )

    assert evaluation["total"] == 3
    assert evaluation["hits"] == 3
    assert evaluation["hit_rate"] == 1.0


def test_evaluate_retrieval_should_report_case_results():
    results = [
        make_result(
            "correct",
            "Python函数可以封装重复逻辑。",
            5.0,
        )
    ]

    cases = [
        RetrievalEvaluationCase(
            query="Python函数有什么作用？",
            expected_chunk_id="correct",
        )
    ]

    def retriever(query, k):
        return results

    evaluation = evaluate_retrieval(
        retriever,
        cases,
        k=1,
    )

    assert len(evaluation["cases"]) == 1

    case_result = evaluation["cases"][0]

    assert case_result.query == "Python函数有什么作用？"
    assert case_result.expected_chunk_id == "correct"
    assert case_result.retrieved_chunk_ids == ["correct"]
    assert case_result.hit is True


def test_evaluate_retrieval_should_report_failed_case():
    results = [
        make_result(
            "wrong",
            "Python变量用于保存数据。",
            5.0,
        )
    ]

    cases = [
        RetrievalEvaluationCase(
            query="Python函数有什么作用？",
            expected_chunk_id="correct",
        )
    ]

    def retriever(query, k):
        return results

    evaluation = evaluate_retrieval(
        retriever,
        cases,
        k=1,
    )

    case_result = evaluation["cases"][0]

    assert case_result.hit is False
    assert case_result.retrieved_chunk_ids == ["wrong"]
