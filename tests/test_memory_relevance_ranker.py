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


def test_score_memory_should_rank_semantic_alias_above_token_distractor():
    semantic_memory = {
        "memory_key": "learning_feedback:external-tools",
        "content": "学习如何让智能体调用外部工具",
    }

    distractor_memory = {
        "memory_key": "learning_feedback:agent-planning",
        "content": "Agent planning notes",
    }

    semantic_score = score_memory(
        semantic_memory,
        query="Agent Tool Calling",
    )

    distractor_score = score_memory(
        distractor_memory,
        query="Agent Tool Calling",
    )

    assert semantic_score > distractor_score


def test_score_memory_should_penalize_semantic_distractor():

    relevant = {
        "memory_key": "learning_feedback:tool-calling",
        "content": "Agent Tool Calling design",
    }

    distractor = {
        "memory_key": "learning_feedback:english-tool",
        "content": "English tool vocabulary",
    }

    query = "Tool Calling"

    assert score_memory(
        relevant,
        query,
    ) > score_memory(
        distractor,
        query,
    )


def test_rank_memories_should_filter_low_score_results():

    memories = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Agent Tool Calling design",
        },
        {
            "memory_key": "learning_feedback:english-tool",
            "content": "English tool vocabulary",
        },
        {
            "memory_key": "learning_feedback:reading",
            "content": "Reading habit",
        },
    ]

    results = rank_memories(
        memories,
        "Tool Calling",
        threshold=0.5,
    )

    keys = [item["memory_key"] for item in results]

    assert "learning_feedback:tool-calling" in keys

    assert "learning_feedback:english-tool" not in keys


def test_score_memory_should_penalize_keyword_only_distractor():

    relevant = {
        "memory_key": "learning_feedback:tool-calling",
        "content": ("Agent Tool Calling interface design"),
    }

    distractor = {
        "memory_key": "learning_feedback:english-tool",
        "content": ("English vocabulary tool word"),
    }

    query = "Tool Calling"

    assert score_memory(
        relevant,
        query,
    ) > score_memory(
        distractor,
        query,
    )


def test_score_memory_should_penalize_domain_mismatch():

    query = "Tool Calling"

    relevant = {
        "memory_key": "learning_feedback:tool-calling",
        "content": ("Agent Tool Calling interface design"),
    }

    distractor = {
        "memory_key": "learning_feedback:english-tool",
        "content": ("English vocabulary word learning"),
    }

    assert score_memory(
        relevant,
        query,
    ) >= score_memory(
        distractor,
        query,
    )


def test_score_memory_should_penalize_unrelated_domain_terms():

    query = "Tool Calling"

    distractor = {
        "memory_key": "learning_feedback:english-tool",
        "content": ("English vocabulary tool word learning"),
    }

    score = score_memory(
        distractor,
        query,
    )

    assert score < 0.5
