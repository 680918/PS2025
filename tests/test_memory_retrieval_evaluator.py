import pytest
from memory.retrieval_evaluator import (
    calculate_f1,
    calculate_precision_at_k,
    calculate_recall_at_k,
    evaluate_retrieval_quality,
    evaluate_retrieval_quality_by_k,
    evaluate_retrieval_recall,
)


def test_calculate_recall_at_k_should_return_full_recall():
    retrieved_keys = [
        "learning_feedback:python-tool-calling",
        "learning_feedback:python-basics",
    ]

    relevant_keys = {
        "learning_feedback:python-tool-calling",
        "learning_feedback:python-basics",
    }

    recall = calculate_recall_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert recall == 1.0


def test_calculate_recall_at_k_should_return_partial_recall():
    retrieved_keys = [
        "learning_feedback:python-tool-calling",
        "learning_feedback:english",
    ]

    relevant_keys = {
        "learning_feedback:python-tool-calling",
        "learning_feedback:python-basics",
    }

    recall = calculate_recall_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert recall == 0.5


def test_calculate_recall_at_k_should_return_zero_when_nothing_matches():
    retrieved_keys = [
        "learning_feedback:english",
    ]

    relevant_keys = {
        "learning_feedback:python-tool-calling",
        "learning_feedback:python-basics",
    }

    recall = calculate_recall_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert recall == 0.0


def test_calculate_recall_at_k_should_return_zero_when_no_relevant_memory():
    retrieved_keys = [
        "learning_feedback:python",
    ]

    relevant_keys = set()

    recall = calculate_recall_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert recall == 0.0


def test_evaluate_retrieval_recall_should_measure_ranked_top_k():
    memories = [
        {
            "memory_key": "learning_feedback:english",
            "content": "English vocabulary review",
        },
        {
            "memory_key": "learning_feedback:python-tool-calling",
            "content": "Python Tool Calling practice",
        },
        {
            "memory_key": "learning_feedback:python-basics",
            "content": "Python basics",
        },
    ]

    relevant_keys = {
        "learning_feedback:python-tool-calling",
        "learning_feedback:python-basics",
    }

    recall = evaluate_retrieval_recall(
        memories,
        query="Python Tool Calling",
        relevant_keys=relevant_keys,
        top_k=2,
    )

    assert recall == 1.0


def test_evaluate_retrieval_recall_should_expose_semantic_ranking_gap():
    memories = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Agent Tool Calling practice",
        },
        {
            "memory_key": "learning_feedback:agent-planning",
            "content": "Agent planning notes",
        },
        {
            "memory_key": "learning_feedback:external-tools",
            "content": "学习如何让智能体调用外部工具",
        },
    ]

    relevant_keys = {
        "learning_feedback:tool-calling",
        "learning_feedback:external-tools",
    }

    recall = evaluate_retrieval_recall(
        memories,
        query="Agent Tool Calling",
        relevant_keys=relevant_keys,
        top_k=2,
    )

    assert recall == 1.0


def test_calculate_precision_at_k_should_return_full_precision():
    retrieved_keys = [
        "learning_feedback:tool-calling",
        "learning_feedback:external-tools",
    ]

    relevant_keys = {
        "learning_feedback:tool-calling",
        "learning_feedback:external-tools",
    }

    precision = calculate_precision_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert precision == 1.0


def test_calculate_precision_at_k_should_return_partial_precision():
    retrieved_keys = [
        "learning_feedback:tool-calling",
        "learning_feedback:english",
    ]

    relevant_keys = {
        "learning_feedback:tool-calling",
        "learning_feedback:external-tools",
    }

    precision = calculate_precision_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert precision == 0.5


def test_calculate_precision_at_k_should_return_zero_when_nothing_matches():
    retrieved_keys = [
        "learning_feedback:english",
    ]

    relevant_keys = {
        "learning_feedback:tool-calling",
        "learning_feedback:external-tools",
    }

    precision = calculate_precision_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert precision == 0.0


def test_calculate_precision_at_k_should_return_zero_when_nothing_retrieved():
    retrieved_keys = []

    relevant_keys = {
        "learning_feedback:tool-calling",
    }

    precision = calculate_precision_at_k(
        retrieved_keys,
        relevant_keys,
    )

    assert precision == 0.0


def test_evaluate_retrieval_quality_should_report_recall_and_precision():
    memories = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Agent Tool Calling practice",
        },
        {
            "memory_key": "learning_feedback:external-tools",
            "content": "学习如何让智能体调用外部工具",
        },
        {
            "memory_key": "learning_feedback:agent-planning",
            "content": "Agent planning notes",
        },
    ]

    relevant_keys = {
        "learning_feedback:tool-calling",
        "learning_feedback:external-tools",
    }

    result = evaluate_retrieval_quality(
        memories,
        query="Agent Tool Calling",
        relevant_keys=relevant_keys,
        top_k=3,
    )

    assert result["recall_at_k"] == 1.0

    assert result["precision_at_k"] == 2 / 3

    assert result["f1_at_k"] == 0.8


def test_evaluate_retrieval_quality_by_k_should_show_quality_tradeoff():
    memories = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Agent Tool Calling practice",
        },
        {
            "memory_key": "learning_feedback:external-tools",
            "content": "学习如何让智能体调用外部工具",
        },
        {
            "memory_key": "learning_feedback:agent-planning",
            "content": "Agent planning notes",
        },
    ]

    relevant_keys = {
        "learning_feedback:tool-calling",
        "learning_feedback:external-tools",
    }

    result = evaluate_retrieval_quality_by_k(
        memories,
        query="Agent Tool Calling",
        relevant_keys=relevant_keys,
        k_values=[1, 2, 3],
    )

    assert result[1]["recall_at_k"] == 0.5
    assert result[1]["precision_at_k"] == 1.0

    assert result[2]["recall_at_k"] == 1.0
    assert result[2]["precision_at_k"] == 1.0

    assert result[3]["recall_at_k"] == 1.0
    assert result[3]["precision_at_k"] == 2 / 3


def test_calculate_f1_should_return_one_for_perfect_retrieval():
    f1 = calculate_f1(
        precision=1.0,
        recall=1.0,
    )

    assert f1 == 1.0


def test_calculate_f1_should_return_zero_when_precision_and_recall_are_zero():
    f1 = calculate_f1(
        precision=0.0,
        recall=0.0,
    )

    assert f1 == 0.0


def test_evaluate_retrieval_quality_should_support_threshold():

    memories = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Agent Tool Calling design",
        },
        {
            "memory_key": "learning_feedback:english-tool",
            "content": "English vocabulary tool word",
        },
    ]

    result = evaluate_retrieval_quality(
        memories,
        query="Tool Calling",
        relevant_keys={
            "learning_feedback:tool-calling",
        },
        top_k=2,
        threshold=0.5,
    )

    assert result["precision_at_k"] == 1.0


def test_evaluate_retrieval_quality_should_report_retrieved_count():

    memories = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Agent Tool Calling design",
        },
        {
            "memory_key": "learning_feedback:python-basics",
            "content": "Python basics",
        },
        {
            "memory_key": "learning_feedback:english",
            "content": "English vocabulary",
        },
    ]

    result = evaluate_retrieval_quality(
        memories,
        query="Tool Calling",
        relevant_keys={"learning_feedback:tool-calling"},
        top_k=3,
    )

    assert result["retrieved_count"] == 3


def test_evaluate_retrieval_quality_should_report_compression_ratio():

    memories = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Agent Tool Calling design",
        },
        {
            "memory_key": "learning_feedback:english-tool",
            "content": "English vocabulary tool",
        },
        {
            "memory_key": "learning_feedback:reading",
            "content": "Reading habit",
        },
    ]

    result = evaluate_retrieval_quality(
        memories,
        query="Tool Calling",
        relevant_keys={"learning_feedback:tool-calling"},
        top_k=3,
        score_gap_threshold=0.4,
    )

    assert result["compression_ratio"] == pytest.approx(2 / 3)
