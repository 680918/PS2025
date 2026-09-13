from evaluation.rag_evaluator import (
    RAGEvaluationCase,
    evaluate_answer,
)


def test_rag_evaluator_should_pass_when_all_keywords_exist():
    case = RAGEvaluationCase(
        query="Python函数有什么作用？",
        expected_keywords=[
            "封装",
            "参数",
            "返回",
        ],
    )

    answer = "Python函数可以封装可重复使用的逻辑，可以接收参数，并返回结果。"

    result = evaluate_answer(
        answer,
        case,
    )

    assert result.passed is True
    assert result.missing_keywords == []


def test_rag_evaluator_should_fail_when_keyword_missing():
    case = RAGEvaluationCase(
        query="Python函数有什么作用？",
        expected_keywords=[
            "封装",
            "参数",
            "返回",
        ],
    )

    answer = "Python函数可以封装重复逻辑。"

    result = evaluate_answer(
        answer,
        case,
    )

    assert result.passed is False
    assert "参数" in result.missing_keywords
    assert "返回" in result.missing_keywords


def test_out_of_scope_answer_should_pass_when_boundary_is_clear():
    case = RAGEvaluationCase(
        query="Python类有什么作用？",
        expected_keywords=[],
        expected_boundary_keywords=[
            "知识库",
            "没有",
            "通用知识",
        ],
    )

    answer = "当前知识库没有关于 Python 类的资料。下面基于通用知识进行说明。"

    result = evaluate_answer(
        answer,
        case,
    )

    assert result.passed is True


def test_out_of_scope_answer_should_fail_when_boundary_is_missing():
    case = RAGEvaluationCase(
        query="Python类有什么作用？",
        expected_keywords=[],
        expected_boundary_keywords=[
            "知识库",
            "没有",
            "通用知识",
        ],
    )

    answer = "Python 类用于封装数据和行为，也支持继承和多态。"

    result = evaluate_answer(
        answer,
        case,
    )

    assert result.passed is False
