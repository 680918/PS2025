import pytest
import memory.memory_score_fusion as score_fusion

from memory.memory_score_fusion import (
    calculate_memory_score,
    rank_memories_by_composite_score,
)


def test_memory_score_should_combine_relevance_importance_and_confidence():
    memory = {
        "importance": 0.8,
        "confidence": 0.9,
    }

    score = calculate_memory_score(
        memory,
        relevance_score=1.0,
    )

    assert score == pytest.approx(1.0 * 0.6 + 0.8 * 0.25 + 0.9 * 0.15)


def test_memory_score_should_default_missing_quality_signals_to_zero():
    memory = {}

    score = calculate_memory_score(
        memory,
        relevance_score=0.5,
    )

    assert score == pytest.approx(0.5 * 0.6)


def test_relevant_memory_should_outscore_unrelated_high_quality_memory():
    relevant_memory = {
        "importance": 0.5,
        "confidence": 0.5,
    }

    unrelated_memory = {
        "importance": 1.0,
        "confidence": 1.0,
    }

    relevant_score = calculate_memory_score(
        relevant_memory,
        relevance_score=1.0,
    )

    unrelated_score = calculate_memory_score(
        unrelated_memory,
        relevance_score=0.0,
    )

    assert relevant_score > unrelated_score


def test_composite_ranking_should_use_memory_quality_to_break_relevance_tie():
    memories = [
        {
            "memory_key": "low-quality",
            "content": "AI Agent memory retrieval",
            "importance": 0.2,
            "confidence": 0.2,
        },
        {
            "memory_key": "high-quality",
            "content": "AI Agent memory retrieval",
            "importance": 0.9,
            "confidence": 0.9,
        },
    ]

    ranked = rank_memories_by_composite_score(
        memories,
        query="AI Agent memory retrieval",
    )

    assert ranked[0]["memory_key"] == "high-quality"
    assert ranked[1]["memory_key"] == "low-quality"


def test_composite_ranking_should_keep_relevance_as_primary_signal():
    memories = [
        {
            "memory_key": "unrelated-high-quality",
            "content": "Cooking and travel notes",
            "importance": 1.0,
            "confidence": 1.0,
        },
        {
            "memory_key": "relevant-lower-quality",
            "content": "AI Agent memory retrieval practice",
            "importance": 0.2,
            "confidence": 0.2,
        },
    ]

    ranked = rank_memories_by_composite_score(
        memories,
        query="AI Agent memory retrieval",
    )

    assert ranked[0]["memory_key"] == "relevant-lower-quality"


def test_composite_ranking_should_protect_relevance_at_guard_threshold(
    monkeypatch,
):
    memories = [
        {
            "memory_key": "more-relevant",
            "content": "memory a",
            "importance": 0.2,
            "confidence": 0.2,
        },
        {
            "memory_key": "higher-quality",
            "content": "memory b",
            "importance": 0.9,
            "confidence": 0.9,
        },
    ]

    relevance_scores = {
        "more-relevant": 0.70,
        "higher-quality": 0.62,
    }

    monkeypatch.setattr(
        score_fusion,
        "score_memory",
        lambda memory, query: relevance_scores[memory["memory_key"]],
    )

    ranked = score_fusion.rank_memories_by_composite_score(
        memories,
        query="test query",
    )

    assert ranked[0]["memory_key"] == "more-relevant"
    assert ranked[1]["memory_key"] == "higher-quality"
