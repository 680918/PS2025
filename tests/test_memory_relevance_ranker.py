from memory.relevance_ranker import (
    rank_memories,
    score_memory,
)


def test_score_memory_should_return_numeric_score():
    memory = {
        "memory_key": "learning_feedback:001",
        "content": "Python Tool Calling practice",
    }

    score = score_memory(
        memory,
        query="Python Tool Calling",
    )

    assert isinstance(score, float)


def test_score_memory_should_rank_keyword_match_higher():
    relevant_memory = {
        "memory_key": "learning_feedback:001",
        "content": "Python Tool Calling practice",
    }

    unrelated_memory = {
        "memory_key": "learning_feedback:002",
        "content": "English vocabulary review",
    }

    relevant_score = score_memory(
        relevant_memory,
        query="Python Tool Calling",
    )

    unrelated_score = score_memory(
        unrelated_memory,
        query="Python Tool Calling",
    )

    assert relevant_score > unrelated_score


def test_score_memory_should_rank_full_match_above_partial_match():
    query = "Python Tool Calling"

    full_match_memory = {
        "memory_key": "learning_feedback:001",
        "content": "Python Tool Calling practice",
    }

    partial_match_memory = {
        "memory_key": "learning_feedback:002",
        "content": "Python basics",
    }

    unrelated_memory = {
        "memory_key": "learning_feedback:003",
        "content": "English vocabulary review",
    }

    full_score = score_memory(
        full_match_memory,
        query=query,
    )

    partial_score = score_memory(
        partial_match_memory,
        query=query,
    )

    unrelated_score = score_memory(
        unrelated_memory,
        query=query,
    )

    assert full_score > partial_score
    assert partial_score > unrelated_score


def test_score_memory_should_handle_punctuation_and_hyphens():
    memory = {
        "memory_key": "learning_feedback:001",
        "content": "Python, tool-calling practice",
    }

    score = score_memory(
        memory,
        query="Python Tool Calling",
    )

    assert score == 1.0


def test_score_memory_should_find_relevance_in_chinese_text():
    memory = {
        "memory_key": "learning_feedback:001",
        "content": "我已经理解工具调用的基本概念",
    }

    score = score_memory(
        memory,
        query="工具调用",
    )

    assert score > 0.0


def test_rank_memories_should_order_by_relevance():
    memories = [
        {
            "memory_key": "learning_feedback:english",
            "content": "English vocabulary review",
        },
        {
            "memory_key": "learning_feedback:python",
            "content": "Python Tool Calling practice",
        },
        {
            "memory_key": "learning_feedback:python-basics",
            "content": "Python basics",
        },
    ]

    ranked = rank_memories(
        memories,
        query="Python Tool Calling",
    )

    ranked_keys = [memory["memory_key"] for memory in ranked]

    assert ranked_keys == [
        "learning_feedback:python",
        "learning_feedback:python-basics",
        "learning_feedback:english",
    ]


def test_rank_memories_should_limit_results_with_top_k():
    memories = [
        {
            "memory_key": "learning_feedback:english",
            "content": "English vocabulary review",
        },
        {
            "memory_key": "learning_feedback:python",
            "content": "Python Tool Calling practice",
        },
        {
            "memory_key": "learning_feedback:python-basics",
            "content": "Python basics",
        },
    ]

    ranked = rank_memories(
        memories,
        query="Python Tool Calling",
        top_k=2,
    )

    ranked_keys = [memory["memory_key"] for memory in ranked]

    assert ranked_keys == [
        "learning_feedback:python",
        "learning_feedback:python-basics",
    ]
