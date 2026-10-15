from dataclasses import dataclass
from agent.context_policy import (
    get_conflict_priority,
    get_policy_name,
)


@dataclass
class ContextConflictResolution:
    source: str
    value: object
    reason: str = None
    policy: str = None


def resolve_context_conflict(
    assembled_context,
    candidates,
):
    source = assembled_context.preferred_source(
        candidates.keys(),
    )

    if source is None:
        return ContextConflictResolution(
            source=None,
            value=None,
        )

    return ContextConflictResolution(
        source=source,
        value=candidates[source],
        reason="source_priority",
    )


def detect_field_conflict(
    assembled_context,
    field_name,
):
    source_values = {
        "learning_continuity": assembled_context.learning_continuity,
        "memory": assembled_context.memory_context,
    }

    candidates = {}

    for source in assembled_context.source_priority:
        context = source_values.get(source)

        if not isinstance(context, dict):
            continue

        if field_name not in context:
            continue

        candidates[source] = context[field_name]

    if len(candidates) < 2:
        return {}

    values = list(candidates.values())

    if all(value == values[0] for value in values[1:]):
        return {}

    return candidates


def resolve_field_conflict(
    assembled_context,
    field_name,
):
    candidates = detect_field_conflict(
        assembled_context=assembled_context,
        field_name=field_name,
    )

    return resolve_context_conflict(
        assembled_context=assembled_context,
        candidates=candidates,
    )


def detect_projection_conflicts(
    projected_contexts,
):
    conflicts = {}

    field_values = {}

    for source, facts in projected_contexts.items():
        for field, value in facts.items():
            if field not in field_values:
                field_values[field] = []

            field_values[field].append(value)

    for field, values in field_values.items():
        unique_values = []

        for value in values:
            if value not in unique_values:
                unique_values.append(value)

        if len(unique_values) > 1:
            conflicts[field] = unique_values

    return conflicts


def resolve_projection_conflict(
    assembled_context,
    projected_contexts,
    field_name,
):
    candidates = {}

    for source, facts in projected_contexts.items():
        if not isinstance(facts, dict):
            continue

        if field_name not in facts:
            continue

        candidates[source] = facts[field_name]

    policy_priority = get_conflict_priority(
        field_name,
    )

    policy_name = get_policy_name(
        field_name,
    )

    source = None

    for preferred_source in policy_priority:
        if preferred_source in candidates:
            source = preferred_source
            break

    if source is None:
        return ContextConflictResolution(
            source=None,
            value=None,
        )

    return ContextConflictResolution(
        source=source,
        value=candidates[source],
        reason="field_policy",
        policy=policy_name,
    )
