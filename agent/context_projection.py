import json


def project_conversation_context(
    conversation_context,
):
    facts = {}

    if not isinstance(
        conversation_context,
        list,
    ):
        return facts

    for message in reversed(
        conversation_context,
    ):
        if not isinstance(
            message,
            dict,
        ):
            continue

        content = message.get(
            "content",
            "",
        )

        if "learn" in content.lower():
            facts["learning.current_topic"] = content
            break

    return facts


def project_learning_continuity(
    continuity,
):
    facts = {}

    if (
        continuity.get("has_current_session") is True
        and continuity.get("current_topic") is not None
    ):
        facts["learning.current_topic"] = continuity["current_topic"]

    if (
        continuity.get("has_current_session") is True
        and continuity.get("current_understanding_score") is not None
    ):
        facts["learning.current_understanding"] = continuity[
            "current_understanding_score"
        ]

    if (
        continuity.get("has_current_session") is True
        and continuity.get("current_difficulty") is not None
    ):
        facts["learning.current_difficulty"] = continuity["current_difficulty"]

    if (
        continuity.get("has_current_session") is True
        and continuity.get("current_next_step") is not None
    ):
        facts["learning.current_next_step"] = continuity["current_next_step"]

    if (
        continuity.get("has_previous_session") is True
        and continuity.get("topic") is not None
    ):
        facts["learning.previous_topic"] = continuity["topic"]

    if (
        continuity.get("has_previous_session") is True
        and continuity.get("understanding_score") is not None
    ):
        facts["learning.previous_understanding"] = continuity["understanding_score"]

    if (
        continuity.get("has_previous_session") is True
        and continuity.get("difficulty") is not None
    ):
        facts["learning.previous_difficulty"] = continuity["difficulty"]

    if (
        continuity.get("has_previous_session") is True
        and continuity.get("next_step") is not None
    ):
        facts["learning.previous_next_step"] = continuity["next_step"]

    return facts


def project_learning_memory(
    memory_context,
):
    facts = {}

    learning_memories = memory_context.get(
        "learning",
        [],
    )

    completed_journeys = []

    for memory in learning_memories:
        memory_key = memory.get("memory_key", "")

        if not memory_key.startswith("journey_completion:"):
            continue

        content = memory.get("content")

        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            continue

        journey = {
            "journey_id": parsed.get("journey_id"),
            "domain": parsed.get("domain"),
            "understanding": parsed.get("latest_understanding"),
        }

        completed_journeys.append(
            journey,
        )

    if len(completed_journeys) == 1:
        journey = completed_journeys[0]

        if journey["domain"] is not None:
            facts["learning.completed_domain"] = journey["domain"]

        if journey["understanding"] is not None:
            facts["learning.completed_understanding"] = journey["understanding"]

    elif len(completed_journeys) > 1:
        facts["learning.completed_journeys"] = completed_journeys

    return facts
