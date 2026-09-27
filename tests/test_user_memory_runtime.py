from memory.runtime import (
    create_user_memory_service,
)


def test_user_memory_services_should_isolate_memories(
    tmp_path,
):
    user_a_memory = create_user_memory_service(
        database_dir=tmp_path,
        user_id="user_a",
    )

    user_b_memory = create_user_memory_service(
        database_dir=tmp_path,
        user_id="user_b",
    )

    user_a_memory.remember(
        memory_type="learning",
        memory_key="journey_completion:journey_001",
        content='{"domain": "Python"}',
        importance=0.9,
        confidence=0.95,
        source="journey_completion_report",
    )

    assert (
        user_a_memory.get_by_key(
            "learning",
            "journey_completion:journey_001",
        )
        is not None
    )

    assert (
        user_b_memory.get_by_key(
            "learning",
            "journey_completion:journey_001",
        )
        is None
    )


def test_same_user_memory_should_persist_across_service_restart(
    tmp_path,
):
    first_service = create_user_memory_service(
        database_dir=tmp_path,
        user_id="user_a",
    )

    first_service.remember(
        memory_type="learning",
        memory_key="journey_completion:journey_001",
        content='{"domain": "Python"}',
        importance=0.9,
        confidence=0.95,
        source="journey_completion_report",
    )

    # 模拟应用重启
    second_service = create_user_memory_service(
        database_dir=tmp_path,
        user_id="user_a",
    )

    saved_memory = second_service.get_by_key(
        "learning",
        "journey_completion:journey_001",
    )

    assert saved_memory is not None
    assert saved_memory.content == '{"domain": "Python"}'
