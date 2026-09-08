import json

from memory.memory import (
    get_user_profile_structured,
    get_skill_map_structured,
)


def migrate_user_profile(memory_service):

    old_profile = get_user_profile_structured()

    profile_data = old_profile["data"]

    for memory_key, value in profile_data.items():
        if isinstance(value, list):
            content = json.dumps(
                value,
                ensure_ascii=False,
            )
        else:
            content = str(value)

        memory_service.remember(
            memory_type="profile",
            memory_key=memory_key,
            content=content,
            importance=0.9,
            confidence=1.0,
            source="user_confirmed",
        )


def ensure_user_profile_migrated(memory_service):

    existing = memory_service.get_by_key(
        "profile",
        "goal",
    )

    if existing is not None:
        return False

    migrate_user_profile(memory_service)

    return True


def migrate_skill_map(memory_service):
    old_skill_map = get_skill_map_structured()
    skill_data = old_skill_map["data"]

    for skill_name, skill_info in skill_data.items():
        content = json.dumps(
            skill_info,
            ensure_ascii=False,
        )

        memory_service.remember(
            memory_type="skill",
            memory_key=skill_name,
            content=content,
            importance=0.9,
            confidence=1.0,
            source="user_confirmed",
        )


def ensure_skill_map_migrated(memory_service):
    existing = memory_service.get_by_key(
        "skill",
        "Python",
    )

    if existing is not None:
        return False

    migrate_skill_map(memory_service)

    return True
