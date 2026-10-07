from memory.memory_score_policy import (
    rank_scored_memories_with_relevance_guard,
    should_protect_relevance,
)


def test_relevance_gap_at_threshold_should_be_protected():
    protected = should_protect_relevance(
        higher_relevance_score=0.70,
        lower_relevance_score=0.62,
    )

    assert protected is True


def test_small_relevance_gap_should_not_be_protected():
    protected = should_protect_relevance(
        higher_relevance_score=0.70,
        lower_relevance_score=0.68,
    )

    assert protected is False


def test_relevance_gap_just_below_threshold_should_not_be_protected():
    protected = should_protect_relevance(
        higher_relevance_score=0.70,
        lower_relevance_score=0.621,
    )

    assert protected is False


def test_relevance_guard_ranking_should_protect_threshold_gap():
    scored_items = [
        {
            "memory_key": "more-relevant",
            "relevance_score": 0.70,
            "composite_score": 0.50,
        },
        {
            "memory_key": "higher-quality",
            "relevance_score": 0.62,
            "composite_score": 0.732,
        },
    ]

    ranked = rank_scored_memories_with_relevance_guard(
        scored_items,
    )

    assert ranked[0]["memory_key"] == "more-relevant"
    assert ranked[1]["memory_key"] == "higher-quality"


def test_relevance_guard_ranking_should_allow_composite_within_same_band():
    scored_items = [
        {
            "memory_key": "slightly-more-relevant",
            "relevance_score": 0.70,
            "composite_score": 0.50,
        },
        {
            "memory_key": "higher-quality",
            "relevance_score": 0.68,
            "composite_score": 0.768,
        },
    ]

    ranked = rank_scored_memories_with_relevance_guard(
        scored_items,
    )

    assert ranked[0]["memory_key"] == "higher-quality"
    assert ranked[1]["memory_key"] == "slightly-more-relevant"


def test_relevance_guard_ranking_should_be_stable_with_multiple_memories():
    scored_items = [
        {
            "memory_key": "highest-relevance",
            "relevance_score": 0.70,
            "composite_score": 0.50,
        },
        {
            "memory_key": "same-band-high-quality",
            "relevance_score": 0.68,
            "composite_score": 0.76,
        },
        {
            "memory_key": "lower-band-very-high-quality",
            "relevance_score": 0.60,
            "composite_score": 0.95,
        },
    ]

    ranked = rank_scored_memories_with_relevance_guard(
        scored_items,
    )

    assert [item["memory_key"] for item in ranked] == [
        "same-band-high-quality",
        "highest-relevance",
        "lower-band-very-high-quality",
    ]


def test_relevance_guard_ranking_should_use_recency_to_break_composite_tie():
    scored_items = [
        {
            "memory_key": "older-memory",
            "relevance_score": 0.70,
            "composite_score": 0.70,
            "recency_score": 0.25,
        },
        {
            "memory_key": "newer-memory",
            "relevance_score": 0.70,
            "composite_score": 0.70,
            "recency_score": 1.0,
        },
    ]

    ranked = rank_scored_memories_with_relevance_guard(
        scored_items,
    )

    assert ranked[0]["memory_key"] == "newer-memory"
    assert ranked[1]["memory_key"] == "older-memory"
