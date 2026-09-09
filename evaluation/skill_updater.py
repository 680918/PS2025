import json

from evaluation.skill_resolver import resolve_skill_key


def update_skill_from_evaluation(
    memory_service,
    evaluation_result,
):
    skill_key = resolve_skill_key(
        evaluation_result.topic,
        memory_service,
    )

    if skill_key is None:
        return None

    skill_memory = memory_service.get_by_key(
        "skill",
        skill_key,
    )

    if skill_memory is None:
        return None

    skill_data = json.loads(skill_memory.content)

    skill_data["level"] = evaluation_result.current_understanding
    skill_data["evaluation_status"] = evaluation_result.status
    skill_data["evaluation_confidence"] = evaluation_result.confidence

    updated_content = json.dumps(
        skill_data,
        ensure_ascii=False,
    )

    return memory_service.store.update(
        skill_memory.id,
        content=updated_content,
        confidence=evaluation_result.confidence,
        source="learning_evaluation",
    )
