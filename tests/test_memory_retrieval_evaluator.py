from memory.retrieval_evaluator import (
    calculate_recall_at_k,
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
