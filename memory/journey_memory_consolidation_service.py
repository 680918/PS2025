import json


def consolidate_journey_completion_summary(
    summary,
    memory_service,
):
    journey_id = summary["journey_id"]

    content = json.dumps(
        summary,
        ensure_ascii=False,
    )

    return memory_service.remember(
        memory_type="learning",
        memory_key=f"journey_completion:{journey_id}",
        content=content,
        importance=0.9,
        confidence=0.95,
        source="journey_completion_report",
    )
