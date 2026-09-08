import json


PROFILE_MEMORY_KEYS = [
    "age",
    "technical_level",
    "goal",
    "daily_learning_time",
    "preferred_learning_time",
    "learning_preferences",
    "strength",
    "weakness",
]


JSON_PROFILE_KEYS = {
    "learning_preferences",
    "strength",
    "weakness",
}


def get_user_profile_from_memory(memory_service):

    data = {}

    for memory_key in PROFILE_MEMORY_KEYS:
        memory = memory_service.get_by_key(
            "profile",
            memory_key,
        )

        if memory is None:
            continue

        value = memory.content

        if memory_key == "age":
            value = int(value)

        elif memory_key in JSON_PROFILE_KEYS:
            value = json.loads(value)

        data[memory_key] = value

    return {
        "status": "success",
        "tool_name": "get_user_profile",
        "data": data,
    }


def get_skill_map_from_memory(memory_service):
    memories = memory_service.store.list_by_type("skill")

    data = {}

    for memory in memories:
        if memory.memory_key is None:
            continue

        data[memory.memory_key] = json.loads(memory.content)

    return {
        "status": "success",
        "tool_name": "get_skill_map",
        "data": data,
    }
