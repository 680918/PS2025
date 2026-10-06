import pytest

from memory.memory_score_fusion_evaluator import (
    calculate_minimum_pairwise_margin,
    calculate_pairwise_order_accuracy,
    evaluate_memory_score_fusion,
    evaluate_memory_score_fusion_items,
    score_memory_fusion_items,
)


def test_pairwise_order_accuracy_should_be_full_when_order_is_correct():
    scored_items = [
        {
            "memory_key": "high",
            "expected_rank": 1,
            "score": 0.9,
        },
        {
            "memory_key": "medium",
            "expected_rank": 2,
            "score": 0.6,
        },
        {
            "memory_key": "low",
            "expected_rank": 3,
            "score": 0.2,
        },
    ]

    accuracy = calculate_pairwise_order_accuracy(
        scored_items,
    )

    assert accuracy == 1.0


def test_pairwise_order_accuracy_should_drop_when_one_pair_is_reversed():
    scored_items = [
        {
            "memory_key": "high",
            "expected_rank": 1,
            "score": 0.9,
        },
        {
            "memory_key": "medium",
            "expected_rank": 2,
            "score": 0.2,
        },
        {
            "memory_key": "low",
            "expected_rank": 3,
            "score": 0.6,
        },
    ]

    accuracy = calculate_pairwise_order_accuracy(
        scored_items,
    )

    assert accuracy == 2 / 3


def test_pairwise_order_accuracy_should_ignore_equal_expected_rank():
    scored_items = [
        {
            "memory_key": "high-a",
            "expected_rank": 1,
            "score": 0.9,
        },
        {
            "memory_key": "high-b",
            "expected_rank": 1,
            "score": 0.4,
        },
        {
            "memory_key": "low",
            "expected_rank": 2,
            "score": 0.2,
        },
    ]

    accuracy = calculate_pairwise_order_accuracy(
        scored_items,
    )

    assert accuracy == 1.0


def test_pairwise_order_accuracy_should_return_zero_when_no_comparable_pairs():
    scored_items = [
        {
            "memory_key": "same-a",
            "expected_rank": 1,
            "score": 0.9,
        },
        {
            "memory_key": "same-b",
            "expected_rank": 1,
            "score": 0.4,
        },
    ]

    accuracy = calculate_pairwise_order_accuracy(
        scored_items,
    )

    assert accuracy == 0.0


def test_minimum_pairwise_margin_should_return_smallest_correct_margin():
    scored_items = [
        {
            "memory_key": "high",
            "expected_rank": 1,
            "score": 0.9,
        },
        {
            "memory_key": "medium",
            "expected_rank": 2,
            "score": 0.7,
        },
        {
            "memory_key": "low",
            "expected_rank": 3,
            "score": 0.2,
        },
    ]

    margin = calculate_minimum_pairwise_margin(
        scored_items,
    )

    assert margin == pytest.approx(0.2)


def test_minimum_pairwise_margin_should_be_negative_when_order_is_reversed():
    scored_items = [
        {
            "memory_key": "high",
            "expected_rank": 1,
            "score": 0.4,
        },
        {
            "memory_key": "low",
            "expected_rank": 2,
            "score": 0.6,
        },
    ]

    margin = calculate_minimum_pairwise_margin(
        scored_items,
    )

    assert margin == pytest.approx(-0.2)


def test_minimum_pairwise_margin_should_return_zero_when_no_comparable_pairs():
    scored_items = [
        {
            "memory_key": "same-a",
            "expected_rank": 1,
            "score": 0.9,
        },
        {
            "memory_key": "same-b",
            "expected_rank": 1,
            "score": 0.4,
        },
    ]

    margin = calculate_minimum_pairwise_margin(
        scored_items,
    )

    assert margin == 0.0


def test_evaluate_memory_score_fusion_should_report_accuracy_and_margin():
    scored_items = [
        {
            "memory_key": "high",
            "expected_rank": 1,
            "score": 0.9,
        },
        {
            "memory_key": "medium",
            "expected_rank": 2,
            "score": 0.7,
        },
        {
            "memory_key": "low",
            "expected_rank": 3,
            "score": 0.2,
        },
    ]

    result = evaluate_memory_score_fusion(
        scored_items,
    )

    assert result["pairwise_order_accuracy"] == 1.0
    assert result["minimum_pairwise_margin"] == pytest.approx(0.2)


def test_score_memory_fusion_items_should_use_real_composite_score():
    items = [
        {
            "memory_key": "memory:high",
            "expected_rank": 1,
            "relevance_score": 0.8,
            "importance": 0.9,
            "confidence": 1.0,
        },
    ]

    scored_items = score_memory_fusion_items(
        items,
    )

    assert scored_items[0]["memory_key"] == "memory:high"
    assert scored_items[0]["expected_rank"] == 1
    assert scored_items[0]["score"] == pytest.approx(
        0.8 * 0.60 + 0.9 * 0.25 + 1.0 * 0.15
    )


def test_evaluate_memory_score_fusion_items_should_score_and_evaluate():
    items = [
        {
            "memory_key": "high",
            "expected_rank": 1,
            "relevance_score": 0.9,
            "importance": 0.9,
            "confidence": 0.9,
        },
        {
            "memory_key": "medium",
            "expected_rank": 2,
            "relevance_score": 0.7,
            "importance": 0.7,
            "confidence": 0.7,
        },
        {
            "memory_key": "low",
            "expected_rank": 3,
            "relevance_score": 0.2,
            "importance": 0.2,
            "confidence": 0.2,
        },
    ]

    result = evaluate_memory_score_fusion_items(
        items,
    )

    assert result["pairwise_order_accuracy"] == 1.0
    assert result["minimum_pairwise_margin"] > 0.0
