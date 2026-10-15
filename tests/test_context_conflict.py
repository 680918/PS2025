from agent.context_assembly import assemble_context
from agent.context_conflict import (
    detect_field_conflict,
    resolve_context_conflict,
    resolve_field_conflict,
    detect_projection_conflicts,
    resolve_projection_conflict,
)
from agent.context_projection import (
    project_learning_continuity,
    project_learning_memory,
)


def test_resolve_context_conflict_should_choose_higher_priority_source():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={
            "topic": "Memory",
        },
        memory_context={
            "topic": "Tool Calling",
        },
    )

    result = resolve_context_conflict(
        assembled_context=assembled,
        candidates={
            "learning_continuity": "Memory",
            "memory": "Tool Calling",
        },
    )

    assert result.source == "learning_continuity"
    assert result.value == "Memory"


def test_resolve_context_conflict_should_not_mutate_inputs():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={
            "topic": "Memory",
        },
        memory_context={
            "topic": "Tool Calling",
        },
    )

    candidates = {
        "learning_continuity": "Memory",
        "memory": "Tool Calling",
    }

    original_learning = assembled.learning_continuity.copy()
    original_memory = assembled.memory_context.copy()
    original_candidates = candidates.copy()

    resolve_context_conflict(
        assembled_context=assembled,
        candidates=candidates,
    )

    assert assembled.learning_continuity == original_learning
    assert assembled.memory_context == original_memory
    assert candidates == original_candidates


def test_resolve_context_conflict_should_return_unresolved_when_no_candidate_matches():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    result = resolve_context_conflict(
        assembled_context=assembled,
        candidates={},
    )

    assert result.source is None
    assert result.value is None


def test_detect_field_conflict_should_collect_same_field_from_multiple_sources():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={
            "topic": "Memory",
        },
        memory_context={
            "topic": "Tool Calling",
        },
    )

    candidates = detect_field_conflict(
        assembled_context=assembled,
        field_name="topic",
    )

    assert candidates == {
        "learning_continuity": "Memory",
        "memory": "Tool Calling",
    }


def test_detect_field_conflict_should_return_empty_when_values_are_equal():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={
            "topic": "Memory",
        },
        memory_context={
            "topic": "Memory",
        },
    )

    candidates = detect_field_conflict(
        assembled_context=assembled,
        field_name="topic",
    )

    assert candidates == {}


def test_detect_field_conflict_should_return_empty_when_only_one_source_has_field():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={
            "topic": "Memory",
        },
        memory_context={},
    )

    candidates = detect_field_conflict(
        assembled_context=assembled,
        field_name="topic",
    )

    assert candidates == {}


def test_resolve_field_conflict_should_detect_and_choose_higher_priority_value():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={
            "topic": "Memory",
        },
        memory_context={
            "topic": "Tool Calling",
        },
    )

    result = resolve_field_conflict(
        assembled_context=assembled,
        field_name="topic",
    )

    assert result.source == "learning_continuity"
    assert result.value == "Memory"


def test_resolve_field_conflict_should_return_unresolved_when_no_conflict_exists():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={
            "topic": "Memory",
        },
        memory_context={
            "topic": "Memory",
        },
    )

    result = resolve_field_conflict(
        assembled_context=assembled,
        field_name="topic",
    )

    assert result.source is None
    assert result.value is None


def test_detect_projection_conflicts_should_detect_same_field_from_different_sources():
    projected_contexts = {
        "conversation": {
            "learning.current_topic": "Memory",
        },
        "learning_continuity": {
            "learning.current_topic": "Tool Calling",
        },
    }

    conflicts = detect_projection_conflicts(
        projected_contexts,
    )

    assert conflicts == {
        "learning.current_topic": [
            "Memory",
            "Tool Calling",
        ]
    }


def test_detect_projection_conflicts_should_work_with_multiple_projected_sources():

    conversation_projection = {
        "learning.current_topic": "Memory",
    }

    continuity_projection = project_learning_continuity(
        {
            "has_current_session": True,
            "current_topic": "Tool Calling",
        }
    )

    memory_projection = project_learning_memory(
        {
            "learning": [
                {
                    "memory_key": "journey_completion:agent",
                    "content": ('{"journey_id":"agent","domain":"AI Agent"}'),
                }
            ]
        }
    )

    conflicts = detect_projection_conflicts(
        {
            "conversation": conversation_projection,
            "learning_continuity": continuity_projection,
            "memory": memory_projection,
        }
    )

    assert conflicts == {
        "learning.current_topic": [
            "Memory",
            "Tool Calling",
        ]
    }


def test_resolve_context_conflict_should_prefer_conversation_source():
    from agent.context_assembly import assemble_context

    assembled_context = assemble_context(
        conversation_context={
            "learning.current_topic": "Memory",
        },
        learning_continuity={
            "learning.current_topic": "Tool Calling",
        },
        memory_context={},
        source_priority=[
            "conversation",
            "learning_continuity",
            "memory",
        ],
    )

    result = resolve_context_conflict(
        assembled_context=assembled_context,
        candidates={
            "conversation": "Memory",
            "learning_continuity": "Tool Calling",
        },
    )

    assert result.source == "conversation"
    assert result.value == "Memory"


def test_resolve_projection_conflict_should_resolve_using_source_priority():

    assembled_context = assemble_context(
        conversation_context={},
        learning_continuity={},
        memory_context={},
        source_priority=[
            "conversation",
            "learning_continuity",
            "memory",
        ],
    )

    projected_contexts = {
        "conversation": {
            "learning.current_topic": "Memory",
        },
        "learning_continuity": {
            "learning.current_topic": "Tool Calling",
        },
    }

    result = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="learning.current_topic",
    )

    assert result.source == "conversation"
    assert result.value == "Memory"


def test_resolve_projection_conflict_should_use_field_policy_for_completed_learning():

    from agent.context_assembly import assemble_context

    assembled_context = assemble_context(
        conversation_context={},
        learning_continuity={},
        memory_context={},
    )

    projected_contexts = {
        "conversation": {
            "learning.completed_understanding": 50,
        },
        "memory": {
            "learning.completed_understanding": 85,
        },
    }

    result = resolve_projection_conflict(
        assembled_context=assembled_context,
        projected_contexts=projected_contexts,
        field_name="learning.completed_understanding",
    )

    assert result.source == "memory"
    assert result.value == 85
