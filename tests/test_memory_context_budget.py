from memory.context_budget import (
    apply_memory_context_budget,
    calculate_memory_context_budget_impact,
    calculate_memory_context_usage,
    limit_memory_context_by_budget,
)


def test_memory_context_budget_should_keep_memories_within_limit():
    memories = [
        {
            "memory_key": "memory:one",
            "content": "12345",
        },
        {
            "memory_key": "memory:two",
            "content": "67890",
        },
        {
            "memory_key": "memory:three",
            "content": "abcde",
        },
    ]

    result = limit_memory_context_by_budget(
        memories,
        max_characters=10,
    )

    assert [memory["memory_key"] for memory in result] == [
        "memory:one",
        "memory:two",
    ]


def test_memory_context_budget_should_return_empty_when_first_memory_exceeds_limit():
    memories = [
        {
            "memory_key": "memory:large",
            "content": "1234567890",
        },
    ]

    result = limit_memory_context_by_budget(
        memories,
        max_characters=5,
    )

    assert result == []


def test_memory_context_budget_should_preserve_ranking_when_remaining_budget_is_insufficient():
    memories = [
        {
            "memory_key": "memory:first",
            "content": "12345",
        },
        {
            "memory_key": "memory:second",
            "content": "1234567890",
        },
        {
            "memory_key": "memory:third",
            "content": "abcde",
        },
    ]

    result = limit_memory_context_by_budget(
        memories,
        max_characters=10,
    )

    assert [memory["memory_key"] for memory in result] == [
        "memory:first",
    ]


def test_memory_context_budget_should_skip_memory_larger_than_total_budget():
    memories = [
        {
            "memory_key": "memory:impossible",
            "content": "123456789012345",
        },
        {
            "memory_key": "memory:fits",
            "content": "12345",
        },
    ]

    result = limit_memory_context_by_budget(
        memories,
        max_characters=10,
    )

    assert [memory["memory_key"] for memory in result] == [
        "memory:fits",
    ]


def test_memory_context_usage_should_report_per_type_and_total_characters():
    memory_context = {
        "profile": [
            {
                "memory_key": "profile:one",
                "content": "12345",
            },
            {
                "memory_key": "profile:two",
                "content": "67890",
            },
        ],
        "skill": [],
        "learning": [
            {
                "memory_key": "learning:one",
                "content": "abc",
            },
        ],
        "project": [],
        "experience": [],
    }

    usage = calculate_memory_context_usage(
        memory_context,
    )

    assert usage["by_type"]["profile"] == 10
    assert usage["by_type"]["learning"] == 3
    assert usage["total_characters"] == 13

    assert usage["count_by_type"]["profile"] == 2
    assert usage["count_by_type"]["learning"] == 1
    assert usage["total_memories"] == 3


def test_memory_context_budget_impact_should_report_character_reduction():
    before_usage = {
        "total_characters": 20,
        "total_memories": 4,
    }

    after_usage = {
        "total_characters": 15,
        "total_memories": 3,
    }

    impact = calculate_memory_context_budget_impact(
        before_usage,
        after_usage,
    )

    assert impact["before_characters"] == 20
    assert impact["after_characters"] == 15
    assert impact["reduced_characters"] == 5
    assert impact["reduction_ratio"] == 0.25


def test_memory_context_budget_impact_should_handle_zero_before_characters():
    before_usage = {
        "total_characters": 0,
        "total_memories": 0,
    }

    after_usage = {
        "total_characters": 0,
        "total_memories": 0,
    }

    impact = calculate_memory_context_budget_impact(
        before_usage,
        after_usage,
    )

    assert impact["before_characters"] == 0
    assert impact["after_characters"] == 0
    assert impact["reduced_characters"] == 0
    assert impact["reduction_ratio"] == 0.0


def test_apply_memory_context_budget_should_limit_by_type_without_mutating_original():
    memory_context = {
        "profile": [
            {"memory_key": "profile:one", "content": "12345"},
            {"memory_key": "profile:two", "content": "67890"},
            {"memory_key": "profile:three", "content": "abcde"},
        ],
        "skill": [
            {"memory_key": "skill:one", "content": "1234"},
        ],
        "learning": [
            {"memory_key": "learning:one", "content": "abc"},
            {"memory_key": "learning:two", "content": "def"},
        ],
        "project": [],
        "experience": [],
    }

    limited_context = apply_memory_context_budget(
        memory_context,
        {
            "profile": 10,
            "learning": 3,
        },
    )

    assert [memory["memory_key"] for memory in limited_context["profile"]] == [
        "profile:one",
        "profile:two",
    ]

    assert [memory["memory_key"] for memory in limited_context["learning"]] == [
        "learning:one",
    ]

    assert [memory["memory_key"] for memory in limited_context["skill"]] == [
        "skill:one",
    ]

    assert len(memory_context["profile"]) == 3
    assert len(memory_context["learning"]) == 2
