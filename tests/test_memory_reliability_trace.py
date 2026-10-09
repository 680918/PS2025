from memory.memory_reliability_trace import (
    build_memory_reliability_trace,
)


def _empty_context():
    return {
        "profile": [],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }


def test_memory_reliability_trace_should_summarize_runtime_stages():
    memory_context = _empty_context()

    memory_context["profile"] = [
        {
            "memory_key": "learning_goal",
            "content": "Learn AI Agents.",
        },
    ]

    memory_context["learning"] = [
        {
            "memory_key": "trusted-python",
            "content": "Needs Python practice.",
        },
        {
            "memory_key": "blocked-python",
            "content": "Fully mastered Python.",
            "confidence": 0.0,
        },
        {
            "memory_key": "extra-learning",
            "content": "Extra learning memory.",
        },
    ]

    blocked_by_trust = _empty_context()
    blocked_by_trust["learning"] = [
        memory_context["learning"][1],
    ]

    before_budget = _empty_context()

    before_budget["profile"] = [
        memory_context["profile"][0],
    ]

    before_budget["learning"] = [
        memory_context["learning"][0],
        memory_context["learning"][2],
    ]

    after_budget = _empty_context()

    after_budget["profile"] = [
        memory_context["profile"][0],
    ]

    after_budget["learning"] = [
        memory_context["learning"][0],
    ]

    trace = build_memory_reliability_trace(
        memory_context,
        {
            "blocked_by_trust": (blocked_by_trust),
            "before_budget": (before_budget),
            "after_budget": (after_budget),
        },
    )

    assert trace["candidates"]["total"] == 4

    assert trace["blocked_by_trust"]["total"] == 1

    assert trace["selected_before_budget"]["total"] == 3

    assert trace["removed_by_budget"]["total"] == 1

    assert trace["injected"]["total"] == 2

    assert trace["blocked_by_trust"]["memory_keys_by_type"]["learning"] == [
        "blocked-python",
    ]

    assert trace["removed_by_budget"]["memory_keys_by_type"]["learning"] == [
        "extra-learning",
    ]

    assert trace["injected"]["memory_keys_by_type"]["learning"] == [
        "trusted-python",
    ]

    assert trace["trusted_candidates"]["total"] == 3

    assert trace["not_selected_before_budget"]["total"] == 0


def test_memory_reliability_trace_should_keep_all_memory_types():
    trace = build_memory_reliability_trace(
        _empty_context(),
        {
            "blocked_by_trust": (_empty_context()),
            "before_budget": (_empty_context()),
            "after_budget": (_empty_context()),
        },
    )

    for stage in (
        "candidates",
        "blocked_by_trust",
        "trusted_candidates",
        "not_selected_before_budget",
        "selected_before_budget",
        "removed_by_budget",
        "injected",
    ):
        assert trace[stage]["count_by_type"] == {
            "profile": 0,
            "skill": 0,
            "learning": 0,
            "project": 0,
            "experience": 0,
        }

        assert trace[stage]["memory_keys_by_type"] == {
            "profile": [],
            "skill": [],
            "learning": [],
            "project": [],
            "experience": [],
        }


def test_memory_reliability_trace_should_detect_budget_removals_by_key():
    memory_context = _empty_context()

    first = {
        "memory_key": "first",
        "content": "First.",
    }

    second = {
        "memory_key": "second",
        "content": "Second.",
    }

    memory_context["project"] = [
        first,
        second,
    ]

    before_budget = _empty_context()

    before_budget["project"] = [
        first,
        second,
    ]

    after_budget = _empty_context()

    after_budget["project"] = [
        first,
    ]

    trace = build_memory_reliability_trace(
        memory_context,
        {
            "blocked_by_trust": (_empty_context()),
            "before_budget": (before_budget),
            "after_budget": (after_budget),
        },
    )

    assert trace["removed_by_budget"]["memory_keys_by_type"]["project"] == [
        "second",
    ]


def test_memory_reliability_trace_should_report_not_selected_before_budget():
    memory_context = _empty_context()

    first = {
        "memory_key": "python-practice",
        "content": "Needs Python practice.",
    }

    second = {
        "memory_key": "tool-calling",
        "content": "Tool Calling practice.",
    }

    third = {
        "memory_key": "english-memory",
        "content": "English learning memory.",
    }

    memory_context["learning"] = [
        first,
        second,
        third,
    ]

    before_budget = _empty_context()

    before_budget["learning"] = [
        first,
        second,
    ]

    after_budget = _empty_context()

    after_budget["learning"] = [
        first,
        second,
    ]

    trace = build_memory_reliability_trace(
        memory_context,
        {
            "blocked_by_trust": (_empty_context()),
            "before_budget": (before_budget),
            "after_budget": (after_budget),
        },
    )

    assert trace["trusted_candidates"]["total"] == 3

    assert trace["not_selected_before_budget"]["total"] == 1

    assert trace["not_selected_before_budget"]["memory_keys_by_type"]["learning"] == [
        "english-memory",
    ]

    assert trace["removed_by_budget"]["total"] == 0
